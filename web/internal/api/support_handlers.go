package api

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// Support tickets, the customer's side.
//
// Everything here writes to Postgres and to nothing else. The operators work
// in Telegram, and carrying a ticket to them is admin_bot's job: it reads
// what this writes. The website holds no admin bot token, so a hole in it
// can reach the operators' chat only the way any customer can -- as a ticket.

const (
	// Counted before the upload is read, so a refused request costs little.
	// Generous next to what a person needs: the page checks a file's type
	// and size before sending it, so honest mistakes rarely get this far.
	supportTicketsPerHour  = 10
	supportMessagesPerHour = 40

	// The server-wide ReadTimeout is 30 seconds. A 45 MB screen recording
	// over a phone's uplink needs longer, so upload requests get their own.
	uploadReadTimeout = 10 * time.Minute
	// And the same recording on its way back.
	downloadWriteTimeout = 10 * time.Minute

	// Uploads held in memory at once. A file goes to Postgres as a single
	// value, so each can weigh up to MaxMessageBytes while it is written;
	// past this many the next one waits for a slot instead.
	uploadSlots    = 4
	uploadSlotWait = time.Minute
)

type supportTicketBody struct {
	ID        int64  `json:"id"`
	Subject   string `json:"subject"`
	Status    string `json:"status"`
	CreatedAt int64  `json:"created_at"`
	UpdatedAt int64  `json:"updated_at"`
	ClosedAt  *int64 `json:"closed_at,omitempty"`
	Unread    bool   `json:"unread"`
}

type supportAttachmentBody struct {
	ID        string `json:"id"`
	Name      string `json:"name"`
	Kind      string `json:"kind"` // image | video | file
	Size      int64  `json:"size"`
	Available bool   `json:"available"`
	// Absent once the file has expired, so the page cannot offer a link that
	// answers 410.
	URL string `json:"url,omitempty"`
}

type supportMessageBody struct {
	ID int64 `json:"id"`
	// "user" or "support". The operator's own name is kept for the operators;
	// the customer is answered by support, not by a person.
	Author      string                  `json:"author"`
	Body        string                  `json:"body"`
	CreatedAt   int64                   `json:"created_at"`
	Attachments []supportAttachmentBody `json:"attachments"`
}

func ticketResponse(t store.SupportTicket) supportTicketBody {
	body := supportTicketBody{
		ID:        t.ID,
		Subject:   t.Subject,
		Status:    t.Status,
		CreatedAt: t.CreatedAt.Unix(),
		UpdatedAt: t.UpdatedAt.Unix(),
		Unread:    t.Unread,
	}
	if t.ClosedAt != nil {
		closed := t.ClosedAt.Unix()
		body.ClosedAt = &closed
	}
	return body
}

func messageResponse(m store.SupportMessage) supportMessageBody {
	author := "user"
	if m.Author == "admin" {
		author = "support"
	}
	body := supportMessageBody{
		ID:          m.ID,
		Author:      author,
		Body:        m.Body,
		CreatedAt:   m.CreatedAt.Unix(),
		Attachments: []supportAttachmentBody{},
	}
	for _, a := range m.Attachments {
		attachment := supportAttachmentBody{
			ID:        a.ID,
			Name:      a.FileName,
			Kind:      support.Kind(a.ContentType),
			Size:      a.SizeBytes,
			Available: a.Available,
		}
		if a.Available {
			attachment.URL = "/api/support/attachments/" + a.ID
		}
		body.Attachments = append(body.Attachments, attachment)
	}
	return body
}

// supportOnly hides the whole section while SUPPORT_ENABLED is off: a ticket
// the site accepted with nothing carrying it to an operator is a customer
// waiting on nobody.
func (s *Server) supportOnly(next handlerWithUser) handlerWithUser {
	return func(w http.ResponseWriter, r *http.Request, user *store.User) {
		if !s.cfg.SupportEnabled {
			writeError(w, http.StatusNotFound, "not_found", "Раздел поддержки недоступен.")
			return
		}
		next(w, r, user)
	}
}

func (s *Server) handleSupportTickets(w http.ResponseWriter, r *http.Request, user *store.User) {
	tickets, err := s.store.SupportTickets(r.Context(), user.ID)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	body := make([]supportTicketBody, 0, len(tickets))
	for _, t := range tickets {
		body = append(body, ticketResponse(t))
	}
	writeJSON(w, http.StatusOK, map[string]any{"tickets": body})
}

func (s *Server) handleCreateSupportTicket(w http.ResponseWriter, r *http.Request, user *store.User) {
	if !s.allowSupport(w, r, "support-ticket:"+user.ID, supportTicketsPerHour,
		"Слишком много обращений подряд. Попробуйте через час.") {
		return
	}
	release, ok := s.acquireUploadSlot(w, r)
	if !ok {
		return
	}
	defer release()

	submission, ok := s.readSupportSubmission(w, r, true)
	if !ok {
		return
	}
	id, err := s.store.CreateSupportTicket(r.Context(), user.ID, submission.Subject, submission.Body,
		storeFiles(submission), support.MaxOpenTickets, support.DailyUploadBytes)
	switch {
	case errors.Is(err, store.ErrTooManyOpenTickets):
		writeError(w, http.StatusConflict, "too_many_open", fmt.Sprintf(
			"Открыто уже %d обращения. Закройте решённые или дождитесь ответа по ним.", support.MaxOpenTickets))
		return
	case errors.Is(err, store.ErrUploadQuota):
		writeError(w, http.StatusTooManyRequests, "upload_quota", uploadQuotaMessage)
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}

	s.log.Info("support ticket opened", "ticket", id, "user", user.ID,
		"files", len(submission.Files), "bytes", submission.Bytes())
	writeJSON(w, http.StatusCreated, map[string]int64{"id": id})
}

const uploadQuotaMessage = "Лимит файлов на сегодня исчерпан. Отправьте текст — файлы можно будет приложить завтра."

func (s *Server) handleSupportThread(w http.ResponseWriter, r *http.Request, user *store.User) {
	id, ok := ticketID(w, r)
	if !ok {
		return
	}
	ticket, messages, err := s.store.SupportThread(r.Context(), user.ID, id)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "not_found", "Обращение не найдено.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	// Marked after reading, so this response still carries the flag that
	// tells the page which answer is new.
	if ticket.Unread {
		if err := s.store.MarkSupportTicketRead(r.Context(), user.ID, id); err != nil {
			s.log.Error("mark support ticket read", "ticket", id, "err", err)
		}
	}

	body := make([]supportMessageBody, 0, len(messages))
	for _, m := range messages {
		body = append(body, messageResponse(m))
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"ticket":   ticketResponse(*ticket),
		"messages": body,
	})
}

func (s *Server) handleSupportReply(w http.ResponseWriter, r *http.Request, user *store.User) {
	id, ok := ticketID(w, r)
	if !ok {
		return
	}
	if !s.allowSupport(w, r, "support-message:"+user.ID, supportMessagesPerHour,
		"Слишком много сообщений подряд. Попробуйте через час.") {
		return
	}
	release, ok := s.acquireUploadSlot(w, r)
	if !ok {
		return
	}
	defer release()

	submission, ok := s.readSupportSubmission(w, r, false)
	if !ok {
		return
	}
	err := s.store.AddSupportMessage(r.Context(), user.ID, id, submission.Body,
		storeFiles(submission), support.DailyUploadBytes)
	switch {
	case errors.Is(err, store.ErrNotFound):
		writeError(w, http.StatusNotFound, "not_found", "Обращение не найдено.")
		return
	case errors.Is(err, store.ErrTicketClosed):
		writeError(w, http.StatusConflict, "ticket_closed",
			"Обращение закрыто. Если вопрос остался, создайте новое.")
		return
	case errors.Is(err, store.ErrUploadQuota):
		writeError(w, http.StatusTooManyRequests, "upload_quota", uploadQuotaMessage)
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusCreated, map[string]bool{"ok": true})
}

func (s *Server) handleCloseSupportTicket(w http.ResponseWriter, r *http.Request, user *store.User) {
	id, ok := ticketID(w, r)
	if !ok {
		return
	}
	err := s.store.CloseSupportTicket(r.Context(), user.ID, id)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "not_found", "Обращение не найдено.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "closed"})
}

// handleSupportAttachment hands a file back to the customer it belongs to.
//
// How it is served is decided from the bytes, not from the stored type: the
// head of the file is sniffed again, and only when it really is one of the
// pictures or videos the thread shows is it served inline under that type.
// Anything else -- including whatever an operator sent from Telegram -- goes
// out as a download that the browser will not render. The sandbox policy
// covers the case of the file being opened on its own in a tab.
func (s *Server) handleSupportAttachment(w http.ResponseWriter, r *http.Request, user *store.User) {
	id := r.PathValue("id")
	if !looksLikeUUID(id) {
		writeError(w, http.StatusNotFound, "not_found", "Файл не найден.")
		return
	}
	meta, err := s.store.SupportAttachment(r.Context(), user.ID, id)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "not_found", "Файл не найден.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !meta.Available {
		writeError(w, http.StatusGone, "file_expired", "Файл удалён по сроку хранения.")
		return
	}

	blob := support.NewBlob(r.Context(), meta.SizeBytes, func(ctx context.Context, offset, n int64) ([]byte, error) {
		return s.store.SupportAttachmentChunk(ctx, user.ID, id, offset, n)
	})
	head := make([]byte, support.SniffLen)
	read, err := io.ReadFull(blob, head)
	if err != nil && !errors.Is(err, io.ErrUnexpectedEOF) && !errors.Is(err, io.EOF) {
		s.fail(w, r, err)
		return
	}
	if _, err := blob.Seek(0, io.SeekStart); err != nil {
		s.fail(w, r, err)
		return
	}

	contentType, disposition := "application/octet-stream", "attachment"
	if detected := support.Detect(head[:read]); detected != "" && detected == meta.ContentType {
		contentType = detected
		if detected == "text/plain" {
			contentType = "text/plain; charset=utf-8"
		}
		if support.Inline(detected) {
			disposition = "inline"
		}
	}

	header := w.Header()
	header.Set("Content-Type", contentType)
	header.Set("Content-Disposition", support.ContentDisposition(disposition, meta.FileName))
	header.Set("Content-Security-Policy", "default-src 'none'; sandbox")
	header.Set("Cross-Origin-Resource-Policy", "same-origin")
	// The file never changes under its id, which is what makes a byte range
	// asked for with If-Range safe to answer from it.
	header.Set("ETag", `"`+id+`"`)

	_ = http.NewResponseController(w).SetWriteDeadline(time.Now().Add(downloadWriteTimeout))
	http.ServeContent(w, r, "", time.Time{}, blob)
}

// -- helpers ------------------------------------------------------------------

func (s *Server) allowSupport(w http.ResponseWriter, r *http.Request, bucket string, limit int, message string) bool {
	ok, err := s.store.AllowAttempt(r.Context(), bucket, limit, time.Hour)
	if err != nil {
		s.fail(w, r, err)
		return false
	}
	if !ok {
		writeError(w, http.StatusTooManyRequests, "rate_limited", message)
		return false
	}
	return true
}

// acquireUploadSlot waits for one of the few uploads allowed in memory at
// once. The caller must call release when the files are written.
func (s *Server) acquireUploadSlot(w http.ResponseWriter, r *http.Request) (release func(), ok bool) {
	timer := time.NewTimer(uploadSlotWait)
	defer timer.Stop()
	select {
	case s.uploads <- struct{}{}:
		return func() { <-s.uploads }, true
	case <-r.Context().Done():
		return nil, false
	case <-timer.C:
		writeError(w, http.StatusServiceUnavailable, "busy",
			"Сейчас загружается много файлов. Попробуйте через минуту.")
		return nil, false
	}
}

// readSupportSubmission reads an upload under its own size cap and deadline.
// It writes the error response itself and reports whether to carry on.
func (s *Server) readSupportSubmission(w http.ResponseWriter, r *http.Request, wantSubject bool) (*support.Submission, bool) {
	_ = http.NewResponseController(w).SetReadDeadline(time.Now().Add(uploadReadTimeout))
	r.Body = http.MaxBytesReader(w, r.Body, support.MaxRequestBytes)

	submission, err := support.ReadSubmission(r, wantSubject)
	var problem *support.Problem
	if errors.As(err, &problem) {
		writeError(w, problem.Status, problem.Code, problem.Message)
		return nil, false
	}
	if err != nil {
		s.fail(w, r, err)
		return nil, false
	}
	return submission, true
}

func storeFiles(submission *support.Submission) []store.NewSupportFile {
	files := make([]store.NewSupportFile, 0, len(submission.Files))
	for _, f := range submission.Files {
		files = append(files, store.NewSupportFile{FileName: f.Name, ContentType: f.ContentType, Data: f.Data})
	}
	return files
}

func ticketID(w http.ResponseWriter, r *http.Request) (int64, bool) {
	id, err := strconv.ParseInt(r.PathValue("id"), 10, 64)
	if err != nil || id <= 0 {
		writeError(w, http.StatusNotFound, "not_found", "Обращение не найдено.")
		return 0, false
	}
	return id, true
}

// looksLikeUUID checks the shape before Postgres does. Handing it anything
// else is an error from the driver, which would read as a 500 rather than as
// the 404 it is.
func looksLikeUUID(value string) bool {
	if len(value) != 36 {
		return false
	}
	for i := 0; i < len(value); i++ {
		c := value[i]
		switch i {
		case 8, 13, 18, 23:
			if c != '-' {
				return false
			}
		default:
			if !('0' <= c && c <= '9' || 'a' <= c && c <= 'f' || 'A' <= c && c <= 'F') {
				return false
			}
		}
	}
	return true
}
