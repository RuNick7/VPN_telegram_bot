// Package support holds the rules for what a customer may send to support:
// how much, of which kinds, and how a file is handed back afterwards.
//
// Kept apart from the handlers so every rule can be tested without a database
// or a server, and so the numbers an operator may want to change are in one
// place rather than scattered through request code.
package support

import (
	"strings"
	"time"
)

const (
	MaxSubjectRunes = 120
	// Enough for a detailed report. It also keeps a message, plus the card
	// that introduces it, close to one Telegram message (4096 characters).
	MaxBodyRunes = 4000

	MaxFilesPerMessage = 3
	// Telegram's own ceiling for a photo a bot sends.
	MaxImageBytes    = 10 << 20
	MaxDocumentBytes = 10 << 20
	// Below the 50 MB a bot may upload, with room for the request around it:
	// every file has to survive the trip to the operators' chat.
	MaxVideoBytes = 45 << 20
	// All of one message's files together.
	MaxMessageBytes = 50 << 20
	// MaxRequestBytes bounds a whole upload: the files at their largest plus
	// the text fields and the multipart framing around them.
	MaxRequestBytes = MaxMessageBytes + 1<<20

	// Tickets one customer may have waiting at once. Enough for two unrelated
	// problems and a mistake; not enough to fill the operators' chat.
	MaxOpenTickets = 3
	// Per customer, per rolling day. Files live in Postgres, and this is what
	// bounds how much of it one account can take.
	DailyUploadBytes = 200 << 20

	// How long a ticket's files are kept once nobody has written in it. The
	// thread itself stays; the file turns into a line saying it has expired.
	AttachmentRetention = 90 * 24 * time.Hour
)

// Inline reports whether a type may be shown in the page rather than
// downloaded: pictures and video, which the thread displays in place.
//
// Nothing else, PDF included -- a document rendered on our origin is a
// document with our cookies' neighbours, and a download is all anyone needs.
func Inline(contentType string) bool {
	switch contentType {
	case "image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime":
		return true
	}
	return false
}

// Kind is how the thread draws a file: "image", "video", or "file".
//
// Derived from Inline rather than from the type's prefix, because an
// operator can send anything from Telegram -- an SVG or a GIF included -- and
// drawing those as pictures would ask the browser to render a response the
// server insists on serving as a download.
func Kind(contentType string) string {
	if !Inline(contentType) {
		return "file"
	}
	if strings.HasPrefix(contentType, "image/") {
		return "image"
	}
	return "video"
}

// MaxBytes is the most a single file of this type may weigh.
func MaxBytes(contentType string) int64 {
	switch Kind(contentType) {
	case "video":
		return MaxVideoBytes
	case "image":
		return MaxImageBytes
	}
	return MaxDocumentBytes
}
