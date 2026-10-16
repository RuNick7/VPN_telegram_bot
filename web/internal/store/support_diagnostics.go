package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// Server-check reports, sent by the vpncheck program with a one-time code.
//
// The code was given to the customer by user_bot after they agreed to the
// check (migrations/0016_support_diagnostics.up.sql). It is the request's
// only authorisation, and all it can do is what the customer could do signed
// in: add their own message, with a file, to that one ticket. Nothing here
// grants consent or issues a code -- that happens in the bot, where the
// customer is.

// DiagnosticsGrant is a code that may still send a report.
type DiagnosticsGrant struct {
	TicketID  int64
	Subject   string
	Status    string
	UserID    string
	ExpiresAt time.Time
}

const usableGrant = `
	d.decision = 'granted' AND d.code_expires_at > now() AND d.reported_at IS NULL
`

// DiagnosticsGrant finds the ticket a code is for. ErrNotFound covers every
// reason it cannot be used -- unknown, expired, already used -- so a caller
// learns nothing by trying codes.
func (s *Store) DiagnosticsGrant(ctx context.Context, codeHash []byte) (*DiagnosticsGrant, error) {
	var g DiagnosticsGrant
	err := s.pool.QueryRow(ctx,
		`SELECT t.id, t.subject, t.status, t.user_id::text, d.code_expires_at
		 FROM support_diagnostics d
		 JOIN support_tickets t ON t.id = d.ticket_id
		 WHERE d.code_hash = $1 AND `+usableGrant,
		codeHash).Scan(&g.TicketID, &g.Subject, &g.Status, &g.UserID, &g.ExpiresAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &g, nil
}

// AttachDiagnosticsReport adds the report to the code's ticket as the
// customer's message and uses the code up, in one transaction: a code
// replayed while the first upload is still being written finds it spent.
func (s *Store) AttachDiagnosticsReport(
	ctx context.Context, codeHash []byte, body string, file NewSupportFile, dailyBytes int64,
) (int64, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	// The customer's lock first, then the rows, in the order the site's own
	// message handlers take them: the other order could deadlock against a
	// message the customer is sending from the page at the same moment.
	var userID string
	err = tx.QueryRow(ctx,
		`SELECT t.user_id::text
		 FROM support_diagnostics d
		 JOIN support_tickets t ON t.id = d.ticket_id
		 WHERE d.code_hash = $1`,
		codeHash).Scan(&userID)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, ErrNotFound
	}
	if err != nil {
		return 0, err
	}
	if err := lockCustomer(ctx, tx, userID); err != nil {
		return 0, err
	}
	var requestID, ticketID int64
	var status string
	err = tx.QueryRow(ctx,
		`SELECT d.id, t.id, t.status
		 FROM support_diagnostics d
		 JOIN support_tickets t ON t.id = d.ticket_id
		 WHERE d.code_hash = $1 AND `+usableGrant+`
		 FOR UPDATE OF d, t`,
		codeHash).Scan(&requestID, &ticketID, &status)
	if errors.Is(err, pgx.ErrNoRows) {
		return 0, ErrNotFound
	}
	if err != nil {
		return 0, err
	}
	if status == "closed" {
		return 0, ErrTicketClosed
	}
	files := []NewSupportFile{file}
	if err := checkUploadQuota(ctx, tx, userID, files, dailyBytes); err != nil {
		return 0, err
	}
	messageID, err := insertMessage(ctx, tx, ticketID, body, files)
	if err != nil {
		return 0, err
	}
	// Back in the operators' queue, as any message from the customer puts
	// it. Not marked read: the customer sent this from a program, not from
	// the page with the operators' answers on it.
	if _, err := tx.Exec(ctx,
		`UPDATE support_tickets SET status = 'open', updated_at = now() WHERE id = $1`,
		ticketID); err != nil {
		return 0, err
	}
	if _, err := tx.Exec(ctx,
		`UPDATE support_diagnostics SET reported_at = now(), report_message_id = $2 WHERE id = $1`,
		requestID, messageID); err != nil {
		return 0, err
	}
	return ticketID, tx.Commit(ctx)
}
