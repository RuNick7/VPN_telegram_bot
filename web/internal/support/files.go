package support

import (
	"path"
	"strings"
	"unicode"
	"unicode/utf8"
)

// maxNameRunes caps a stored file name. Long enough for anything a phone
// generates, short enough to fit a header and a line of the thread.
const maxNameRunes = 100

// extensions lists, per accepted type, the endings a file of that type is
// allowed to keep. The first is what gets added when a name has none of them.
var extensions = map[string][]string{
	"image/jpeg":      {".jpg", ".jpeg"},
	"image/png":       {".png"},
	"image/webp":      {".webp"},
	"application/pdf": {".pdf"},
	"text/plain":      {".txt", ".log"},
	"video/mp4":       {".mp4", ".m4v"},
	"video/quicktime": {".mov", ".qt"},
	"video/webm":      {".webm"},
}

// CleanFileName makes a client-supplied name safe to keep and to echo back.
//
// Only the last path element survives (old browsers sent the whole path),
// characters that mean something in a header or a filesystem are dropped,
// and the ending is made to agree with what the content really is: a text
// file called `setup.exe` is saved as `setup.exe.txt`, so a download is
// opened by the program that matches it rather than by the one its name
// asks for.
func CleanFileName(name, contentType string) string {
	if index := strings.LastIndexAny(name, `/\`); index >= 0 {
		name = name[index+1:]
	}

	var cleaned strings.Builder
	for _, r := range name {
		switch {
		case r == utf8.RuneError, unicode.IsControl(r), unicode.Is(unicode.Cf, r):
			// Control and format characters -- the right-to-left override
			// among them, which is how `gpj.exe` is made to display as
			// `exe.jpg`.
			continue
		case strings.ContainsRune(`"<>:|?*`, r):
			continue
		}
		cleaned.WriteRune(r)
	}
	result := strings.Trim(strings.TrimSpace(cleaned.String()), ".")

	allowed := extensions[contentType]
	ext := path.Ext(result)
	if len(allowed) > 0 && !contains(allowed, strings.ToLower(ext)) {
		result += allowed[0]
		ext = allowed[0]
	}
	if strings.TrimSuffix(result, ext) == "" {
		result = "file" + ext
	}

	if utf8.RuneCountInString(result) > maxNameRunes {
		// Cut the stem, never the extension: the extension is what decides
		// which program opens the download.
		stem := []rune(strings.TrimSuffix(result, ext))
		result = string(stem[:maxNameRunes-utf8.RuneCountInString(ext)]) + ext
	}
	return result
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

// ContentDisposition builds the header that serves a file under its own
// name.
//
// Two forms side by side, as RFC 6266 recommends: `filename` with an ASCII
// stand-in for clients that know nothing else, and `filename*` with the real
// name percent-encoded as UTF-8 -- the only way a Cyrillic name arrives
// intact. The name comes from the database, which an operator writes to from
// Telegram, so it is encoded here whatever it contains.
func ContentDisposition(disposition, name string) string {
	return disposition + `; filename="` + asciiFallback(name) + `"; filename*=UTF-8''` + encodeRFC5987(name)
}

// asciiFallback keeps the letters, digits and a little punctuation of a name
// and turns everything else into `_`. Stricter than a quoted string requires:
// `;`, `=` and `'` are legal inside the quotes, but a client that parses the
// header carelessly is exactly the one reading this form of it.
func asciiFallback(name string) string {
	var out strings.Builder
	for _, r := range name {
		switch {
		case 'a' <= r && r <= 'z', 'A' <= r && r <= 'Z', '0' <= r && r <= '9',
			strings.ContainsRune(" .-_()[]+", r):
			out.WriteRune(r)
		default:
			out.WriteByte('_')
		}
	}
	return out.String()
}

// encodeRFC5987 percent-encodes everything outside RFC 5987's attr-char set.
//
// Not url.PathEscape: that leaves `'`, `;` and `=` alone, and each of those
// ends or splits a header parameter.
func encodeRFC5987(value string) string {
	const hex = "0123456789ABCDEF"
	var out strings.Builder
	for i := 0; i < len(value); i++ {
		c := value[i]
		if isAttrChar(c) {
			out.WriteByte(c)
			continue
		}
		out.WriteByte('%')
		out.WriteByte(hex[c>>4])
		out.WriteByte(hex[c&0x0f])
	}
	return out.String()
}

func isAttrChar(c byte) bool {
	switch {
	case 'a' <= c && c <= 'z', 'A' <= c && c <= 'Z', '0' <= c && c <= '9':
		return true
	}
	return strings.IndexByte("!#$&+-.^_`|~", c) >= 0
}
