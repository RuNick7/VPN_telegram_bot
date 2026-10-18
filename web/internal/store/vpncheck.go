package store

import (
	"context"
	"errors"
	"strconv"

	"github.com/jackc/pgx/v5"
)

// Server-check reports, sent by the vpncheck program with the customer's
// subscription link (migrations/0016_vpncheck_reports.up.sql).
//
// The link is the only authorisation, and all it can do is what the customer
// could do signed in: add their own message, with a file, to their own
// ticket, or open one. Nothing here reads a ticket back.

var ErrReportQuota = errors.New("vpncheck report quota exhausted")

// UserByPanelAccount finds whose panel account this is, by the same three
// handles, in the same order, that lead from a user to their account
// (account.EnsureProfile, `resolve_panel_user` in user_bot): the stored panel
// UUID, the stored panel username, and the legacy name `str(telegram_id)`.
// A merged-away row leads on to the row that absorbed it.
func (s *Store) UserByPanelAccount(ctx context.Context, panelRef, panelUsername string) (*User, error) {
	var legacy *int64
	if id, ok := legacyTelegramID(panelUsername); ok {
		legacy = &id
	}
	return scanUser(s.pool.QueryRow(ctx,
		`WITH RECURSIVE start AS (
			SELECT id, merged_into,
			       CASE WHEN remnawave_uuid = $1 THEN 0
			            WHEN remnawave_username = $2 THEN 1
			            ELSE 2 END AS rank
			FROM users
			WHERE ($1 <> '' AND remnawave_uuid = $1)
			   OR ($2 <> '' AND remnawave_username = $2)
			   OR ($3::bigint IS NOT NULL AND telegram_id = $3)
			ORDER BY rank, merged_into IS NOT NULL
			LIMIT 1
		), chain AS (
			SELECT id, merged_into, 0 AS depth FROM start
			UNION ALL
			SELECT u.id, u.merged_into, chain.depth + 1
			FROM users u JOIN chain ON u.id = chain.merged_into
			WHERE chain.depth < 8
		)
		SELECT `+userColumns+` FROM users
		WHERE id = (SELECT id FROM chain WHERE merged_into IS NULL LIMIT 1)`,
		panelRef, panelUsername, legacy))
}

// legacyTelegramID reads a panel name from before the identity rework, which
// is the customer's Telegram id and nothing else.
func legacyTelegramID(username string) (int64, bool) {
	id, err := strconv.ParseInt(username, 10, 64)
	return id, err == nil && id > 0 && strconv.FormatInt(id, 10) == username
}

// AttachVpncheckReport puts a report into the customer's latest open ticket
// as their message, or opens a ticket with it when none is open. Returns the
// ticket and whether it was opened for this.
func (s *Store) AttachVpncheckReport(
	ctx context.Context, userID, subject, body string, file NewSupportFile,
	perDay int, dailyBytes int64,
) (ticketID int64, created bool, err error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return 0, false, err
	}
	defer tx.Rollback(ctx)

	if err := lockCustomer(ctx, tx, userID); err != nil {
		return 0, false, err
	}
	var sent int
	if err := tx.QueryRow(ctx,
		`SELECT COUNT(*) FROM vpncheck_reports r
		 JOIN support_tickets t ON t.id = r.ticket_id
		 WHERE t.user_id = $1 AND r.created_at > now() - interval '24 hours'`,
		userID).Scan(&sent); err != nil {
		return 0, false, err
	}
	if sent >= perDay {
		return 0, false, ErrReportQuota
	}
	files := []NewSupportFile{file}
	if err := checkUploadQuota(ctx, tx, userID, files, dailyBytes); err != nil {
		return 0, false, err
	}

	err = tx.QueryRow(ctx,
		`SELECT id FROM support_tickets
		 WHERE user_id = $1 AND status <> 'closed'
		 ORDER BY updated_at DESC, id DESC
		 LIMIT 1
		 FOR UPDATE`,
		userID).Scan(&ticketID)
	switch {
	case errors.Is(err, pgx.ErrNoRows):
		created = true
		if err := tx.QueryRow(ctx,
			`INSERT INTO support_tickets (user_id, subject) VALUES ($1, $2) RETURNING id`,
			userID, subject).Scan(&ticketID); err != nil {
			return 0, false, err
		}
	case err != nil:
		return 0, false, err
	}
	messageID, err := insertMessage(ctx, tx, ticketID, body, files)
	if err != nil {
		return 0, false, err
	}
	// Back in the operators' queue, as any message from the customer puts
	// it. Not marked read: the customer sent this from a program, not from
	// the page with the operators' answers on it.
	if _, err := tx.Exec(ctx,
		`UPDATE support_tickets SET status = 'open', updated_at = now() WHERE id = $1`,
		ticketID); err != nil {
		return 0, false, err
	}
	if _, err := tx.Exec(ctx,
		`INSERT INTO vpncheck_reports (ticket_id, message_id) VALUES ($1, $2)`,
		ticketID, messageID); err != nil {
		return 0, false, err
	}
	return ticketID, created, tx.Commit(ctx)
}
