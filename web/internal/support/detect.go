package support

import (
	"bytes"
	"unicode/utf8"
)

// SniffLen is how much of a file Detect needs to name its type -- enough for
// every signature below. Text is judged on whatever it is given.
const SniffLen = 512

// Detect names a file's type from its content, or returns "" for anything not
// accepted.
//
// What the browser claims is never consulted. It is whatever the client
// says, and the type decides how the file is served back: an HTML page
// labelled image/png becomes script on our origin the moment it is treated as
// what it really is. So only a short list is recognised, each type by its own
// signature, and everything else is refused.
//
// Given a whole file, text is checked end to end; given only its head, as at
// serve time, just the head.
func Detect(content []byte) string {
	switch {
	case bytes.HasPrefix(content, []byte("\xff\xd8\xff")):
		return "image/jpeg"
	case bytes.HasPrefix(content, []byte("\x89PNG\r\n\x1a\n")):
		return "image/png"
	case len(content) >= 12 && bytes.Equal(content[:4], []byte("RIFF")) && bytes.Equal(content[8:12], []byte("WEBP")):
		return "image/webp"
	case bytes.HasPrefix(content, []byte("%PDF-")):
		return "application/pdf"
	case bytes.HasPrefix(content, []byte("\x1a\x45\xdf\xa3")):
		// EBML, the container WebM is written in -- what a screen recorder in
		// a browser produces.
		return "video/webm"
	}
	if kind := isoMedia(content); kind != "" {
		return kind
	}
	if isPlainText(content) {
		return "text/plain"
	}
	return ""
}

// videoBrands are the `ftyp` major brands of an MP4 a phone or a screen
// recorder actually writes.
var videoBrands = map[string]bool{
	"isom": true, "iso2": true, "iso4": true, "iso5": true, "iso6": true,
	"mp41": true, "mp42": true, "avc1": true, "M4V ": true, "M4VH": true,
	"M4VP": true, "dash": true, "mmp4": true, "MSNV": true,
}

// isoMedia recognises MP4 and QuickTime by their `ftyp` box.
//
// The brand decides which, and it has to be a video brand: HEIC and AVIF
// photos live in the same container, and mistaking one for a video would
// hand the browser a <video> it cannot play.
func isoMedia(content []byte) string {
	if len(content) < 12 || !bytes.Equal(content[4:8], []byte("ftyp")) {
		return ""
	}
	brand := string(content[8:12])
	switch {
	case brand == "qt  ":
		// What an iPhone records, and what Safari uploads a video as.
		return "video/quicktime"
	case videoBrands[brand]:
		return "video/mp4"
	}
	return ""
}

// isPlainText accepts UTF-8 text with no control characters beyond the ones
// text files really contain. An app's log file is the case it exists for.
func isPlainText(content []byte) bool {
	if len(content) == 0 {
		return false
	}
	if !utf8.Valid(trimPartialRune(content)) {
		return false
	}
	for _, c := range content {
		if c == 0x7f || (c < 0x20 && c != '\t' && c != '\n' && c != '\r' && c != '\f' && c != 0x1b) {
			return false
		}
	}
	return true
}

// trimPartialRune drops a multi-byte character cut off at the end, which is
// what reading a fixed-size head of a text file does to it -- not a sign that
// the file is binary.
func trimPartialRune(content []byte) []byte {
	for cut := 1; cut < utf8.UTFMax && cut <= len(content); cut++ {
		if utf8.RuneStart(content[len(content)-cut]) {
			if !utf8.FullRune(content[len(content)-cut:]) {
				return content[:len(content)-cut]
			}
			break
		}
	}
	return content
}
