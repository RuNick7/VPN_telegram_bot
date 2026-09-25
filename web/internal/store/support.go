package store

import (
	"context"
	"errors"
	"time"

	"github.com/jackc/pgx/v5"
)

// Support tickets, as the customer sees them.
//
// Every read and write below names the customer as well as the ticket, and
// the ownership check is in the SQL itself rather than done afterwards: a
// ticket that is not yours is simply not found, whatever its number.
//
// What is missing is deliberate. There is no way here to write an operator's
// answer or to mark a ticket answered -- only admin_bot does that, from the
// operators' own Telegram replies. The website is the most exposed process in
// the deployment, and a hole in it should not be able to speak as support.

var (
	ErrTooManyOpenTickets = errors.New("too many open tickets")
	ErrUploadQuota        = errors.New("daily upload quota exhausted")
	ErrTicketClosed       = errors.New("ticket is closed")
)

type SupportTicket struct {
	ID        int64
	Subject   string
	Status    string // open | answered | closed
	CreatedAt time.Time
	UpdatedAt time.Time
	ClosedAt  *time.Time
	// An operator has written since the customer last opened the thread.
	Unread bool
}

type SupportMessage struct {
	ID          int64
	Author      string // user | admin
	Body        string
	CreatedAt   time.Time
	Attachments []SupportAttachment
}

type SupportAttachment struct {
	ID          string
	MessageID   int64
	FileName    string
	ContentType string
	SizeBytes   int64
	// False once the bytes are gone -- purged for age, or restored from a
	// backup that leaves them out.
	Available bool
}

// NewSupportFile is one file to store with a customer's message.
type NewSupportFile struct {
	FileName    string
	ContentType string
	Data        []byte
}

const ticketColumns = `
	t.id, t.subject, t.status, t.created_at, t.updated_at, t.closed_at,
	EXISTS (
		SELECT 1 FROM support_messages m
		WHERE m.ticket_id = t.id AND m.author = 'admin' AND m.created_at > t.user_read_at
	)
`

func scanTicket(row pgx.Row) (*SupportTicket, error) {
	var t SupportTicket
	err := row.Scan(&t.ID, &t.Subject, &t.Status, &t.CreatedAt, &t.UpdatedAt, &t.ClosedAt, &t.Unread)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &t, nil
}

// lockCustomer serialises one customer's submissions for the rest of the
// transaction. Two tabs submitting at once would otherwise both count two
// open tickets and both open a third, or both fit under the day's quota and
// together overshoot it.
func lockCustomer(ctx context.Context, tx pgx.Tx, userID string) error {
	_, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock(hashtextextended('support:' || $1, 0))`, userID)
	return err
}

// checkUploadQuota refuses files that would take the customer past their
// allowance for the last 24 hours.
func checkUploadQuota(ctx context.Context, tx pgx.Tx, userID string, files []NewSupportFile, dailyBytes int64) error {
	if len(files) == 0 {
		return nil
	}
	var adding int64
	for _, file := range files {
		adding += int64(len(file.Data))
	}
	var used int64
	err := tx.QueryRow(ctx,
		`SELECT COALESCE(SUM(a.size_bytes), 0)
		 FROM support_attachments a
		 JOIN support_messages m ON m.id = a.message_id
		 JOIN support_tickets t ON t.id = m.ticket_id
		 WHERE t.user_id = $1 AND m.author = 'user' AND a.created_at > now() - interval '24 hours'`,
		userID).Scan(&used)
	if err != nil {
		return err
	}
	if used+adding > dailyBytes {
		return ErrUploadQuota
	}
	return nil
}

func insertMessage(ctx context.Context, tx pgx.Tx, ticketID int64, body string, files []NewSupportFile) error {
	var messageID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO support_messages (ticket_id, author, body) VALUES ($1, 'user', $2) RETURNING id`,
		ticketID, body).Scan(&messageID); err != nil {
		return err
	}
	for _, file := range files {
		var attachmentID string
		if err := tx.QueryRow(ctx,
			`INSERT INTO support_attachments (message_id, file_name, content_type, size_bytes)
			 VALUES ($1, $2, $3, $4) RETURNING id`,
			messageID, file.FileName, file.ContentType, len(file.Data)).Scan(&attachmentID); err != nil {
			return err
		}
		if _, err := tx.Exec(ctx,
			`INSERT INTO support_attachment_data (attachment_id, data) VALUES ($1, $2)`,
			attachmentID, file.Data); err != nil {
			return err
		}
	}
	return nil
}

// CreateSupportTicket opens a ticket with its first message, in one
// transaction, and returns its number.
func (s *Store) CreateSupportTicket(
	ctx context.Context, userID, subject, body string, files []NewSupportFile,
	maxOpen int, dailyBytes int64,
) (int64, error) {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return 0, err
	}
	defer tx.Rollback(ctx)

	if err := lockCustomer(ctx, tx, userID); err != nil {
		return 0, err
	}
	var open int
	if err := tx.QueryRow(ctx,
		`SELECT COUNT(*) FROM support_tickets WHERE user_id = $1 AND status <> 'closed'`,
		userID).Scan(&open); err != nil {
		return 0, err
	}
	if open >= maxOpen {
		return 0, ErrTooManyOpenTickets
	}
	if err := checkUploadQuota(ctx, tx, userID, files, dailyBytes); err != nil {
		return 0, err
	}

	var ticketID int64
	if err := tx.QueryRow(ctx,
		`INSERT INTO support_tickets (user_id, subject) VALUES ($1, $2) RETURNING id`,
		userID, subject).Scan(&ticketID); err != nil {
		return 0, err
	}
	if err := insertMessage(ctx, tx, ticketID, body, files); err != nil {
		return 0, err
	}
	return ticketID, tx.Commit(ctx)
}

// AddSupportMessage appends the customer's message to their own open
// ticket, which puts it back in the operators' queue.
//
// A closed ticket takes no more messages: the customer opens a new one. That
// keeps "closed" meaning something to the operators, whose list shows only
// what is waiting on them.
func (s *Store) AddSupportMessage(
	ctx context.Context, userID string, ticketID int64, body string, files []NewSupportFile,
	dailyBytes int64,
) error {
	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return err
	}
	defer tx.Rollback(ctx)

	if err := lockCustomer(ctx, tx, userID); err != nil {
		return err
	}
	var status string
	err = tx.QueryRow(ctx,
		`SELECT status FROM support_tickets WHERE id = $1 AND user_id = $2 FOR UPDATE`,
		ticketID, userID).Scan(&status)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrNotFound
	}
	if err != nil {
		return err
	}
	if status == "closed" {
		return ErrTicketClosed
	}
	if err := checkUploadQuota(ctx, tx, userID, files, dailyBytes); err != nil {
		return err
	}
	if err := insertMessage(ctx, tx, ticketID, body, files); err != nil {
		return err
	}
	// Writing is reading: whatever the operators said, the customer was on
	// the page answering it.
	if _, err := tx.Exec(ctx,
		`UPDATE support_tickets
		 SET status = 'open', updated_at = now(), user_read_at = now()
		 WHERE id = $1`,
		ticketID); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

// SupportTickets lists a customer's tickets: live ones first, then by the
// last thing that happened in them.
func (s *Store) SupportTickets(ctx context.Context, userID string) ([]SupportTicket, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT `+ticketColumns+`
		 FROM support_tickets t
		 WHERE t.user_id = $1
		 ORDER BY (t.status = 'closed'), t.updated_at DESC
		 LIMIT 100`,
		userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var tickets []SupportTicket
	for rows.Next() {
		ticket, err := scanTicket(rows)
		if err != nil {
			return nil, err
		}
		tickets = append(tickets, *ticket)
	}
	return tickets, rows.Err()
}

// SupportThread returns one of the customer's tickets with every message and
// the metadata -- never the bytes -- of every file.
func (s *Store) SupportThread(ctx context.Context, userID string, ticketID int64) (*SupportTicket, []SupportMessage, error) {
	ticket, err := scanTicket(s.pool.QueryRow(ctx,
		`SELECT `+ticketColumns+` FROM support_tickets t WHERE t.id = $1 AND t.user_id = $2`,
		ticketID, userID))
	if err != nil {
		return nil, nil, err
	}

	rows, err := s.pool.Query(ctx,
		`SELECT id, author, body, created_at FROM support_messages WHERE ticket_id = $1 ORDER BY id`,
		ticketID)
	if err != nil {
		return nil, nil, err
	}
	var messages []SupportMessage
	index := map[int64]int{}
	for rows.Next() {
		var m SupportMessage
		if err := rows.Scan(&m.ID, &m.Author, &m.Body, &m.CreatedAt); err != nil {
			rows.Close()
			return nil, nil, err
		}
		index[m.ID] = len(messages)
		messages = append(messages, m)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, nil, err
	}

	rows, err = s.pool.Query(ctx,
		`SELECT a.id, a.message_id, a.file_name, a.content_type, a.size_bytes,
		        EXISTS (SELECT 1 FROM support_attachment_data d WHERE d.attachment_id = a.id)
		 FROM support_attachments a
		 JOIN support_messages m ON m.id = a.message_id
		 WHERE m.ticket_id = $1
		 ORDER BY a.created_at, a.id`,
		ticketID)
	if err != nil {
		return nil, nil, err
	}
	defer rows.Close()
	for rows.Next() {
		var a SupportAttachment
		if err := rows.Scan(&a.ID, &a.MessageID, &a.FileName, &a.ContentType, &a.SizeBytes, &a.Available); err != nil {
			return nil, nil, err
		}
		if i, ok := index[a.MessageID]; ok {
			messages[i].Attachments = append(messages[i].Attachments, a)
		}
	}
	return ticket, messages, rows.Err()
}

// MarkSupportTicketRead records that the customer has seen the thread.
func (s *Store) MarkSupportTicketRead(ctx context.Context, userID string, ticketID int64) error {
	_, err := s.pool.Exec(ctx,
		`UPDATE support_tickets SET user_read_at = now() WHERE id = $1 AND user_id = $2`,
		ticketID, userID)
	return err
}

// CloseSupportTicket closes the customer's own ticket. Closing one that is
// already closed is not an error; one that is not theirs is not found.
func (s *Store) CloseSupportTicket(ctx context.Context, userID string, ticketID int64) error {
	var status string
	err := s.pool.QueryRow(ctx,
		`UPDATE support_tickets SET
		     status     = 'closed',
		     closed_at  = COALESCE(closed_at, now()),
		     closed_by  = COALESCE(closed_by, 'user'),
		     updated_at = CASE WHEN status = 'closed' THEN updated_at ELSE now() END
		 WHERE id = $1 AND user_id = $2
		 RETURNING status`,
		ticketID, userID).Scan(&status)
	if errors.Is(err, pgx.ErrNoRows) {
		return ErrNotFound
	}
	return err
}

// SupportUnread counts the customer's tickets with an answer they have not
// opened -- the dot on the cabinet's support tab.
func (s *Store) SupportUnread(ctx context.Context, userID string) (int, error) {
	var count int
	err := s.pool.QueryRow(ctx,
		`SELECT COUNT(*) FROM support_tickets t
		 WHERE t.user_id = $1 AND EXISTS (
		     SELECT 1 FROM support_messages m
		     WHERE m.ticket_id = t.id AND m.author = 'admin' AND m.created_at > t.user_read_at
		 )`,
		userID).Scan(&count)
	return count, err
}

// SupportAttachment returns a file's metadata if it belongs to one of the
// customer's tickets.
func (s *Store) SupportAttachment(ctx context.Context, userID, attachmentID string) (*SupportAttachment, error) {
	var a SupportAttachment
	err := s.pool.QueryRow(ctx,
		`SELECT a.id, a.message_id, a.file_name, a.content_type, a.size_bytes,
		        EXISTS (SELECT 1 FROM support_attachment_data d WHERE d.attachment_id = a.id)
		 FROM support_attachments a
		 JOIN support_messages m ON m.id = a.message_id
		 JOIN support_tickets t ON t.id = m.ticket_id
		 WHERE a.id = $1 AND t.user_id = $2`,
		attachmentID, userID).Scan(&a.ID, &a.MessageID, &a.FileName, &a.ContentType, &a.SizeBytes, &a.Available)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	if err != nil {
		return nil, err
	}
	return &a, nil
}

// SupportAttachmentChunk reads n bytes of a file from offset.
//
// Ownership is checked on every chunk, not only when the file was looked up:
// it costs a join, and it means no caller can read a byte of a file without
// naming the customer it belongs to.
func (s *Store) SupportAttachmentChunk(ctx context.Context, userID, attachmentID string, offset, n int64) ([]byte, error) {
	var chunk []byte
	err := s.pool.QueryRow(ctx,
		`SELECT substring(d.data FROM $3 FOR $4)
		 FROM support_attachment_data d
		 JOIN support_attachments a ON a.id = d.attachment_id
		 JOIN support_messages m ON m.id = a.message_id
		 JOIN support_tickets t ON t.id = m.ticket_id
		 WHERE d.attachment_id = $1 AND t.user_id = $2`,
		attachmentID, userID, offset+1, n).Scan(&chunk)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, ErrNotFound
	}
	return chunk, err
}

// PurgeStaleSupportAttachments drops the bytes of files in tickets nobody has
// written in for `idle`. The rows stay, so the thread still says a file was
// there. Returns how many files went.
func (s *Store) PurgeStaleSupportAttachments(ctx context.Context, idle time.Duration) (int64, error) {
	cmd, err := s.pool.Exec(ctx,
		`DELETE FROM support_attachment_data d
		 USING support_attachments a, support_messages m, support_tickets t
		 WHERE d.attachment_id = a.id AND a.message_id = m.id AND m.ticket_id = t.id
		   AND t.updated_at < now() - $1::interval`,
		idle.String())
	if err != nil {
		return 0, err
	}
	return cmd.RowsAffected(), nil
}
