package support

import (
	"bytes"
	"context"
	"errors"
	"io"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"net/textproto"
	"strings"
	"testing"
	"time"
)

// -- what a file is ---------------------------------------------------------

var (
	jpeg      = []byte("\xff\xd8\xff\xe0\x00\x10JFIF\x00")
	png       = []byte("\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
	webp      = []byte("RIFF\x24\x00\x00\x00WEBPVP8 ")
	pdf       = []byte("%PDF-1.7\n%\xe2\xe3\xcf\xd3")
	webm      = []byte("\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01")
	mp4       = []byte("\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
	quicktime = []byte("\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00qt  ")
	heic      = []byte("\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic")
)

func TestEachAcceptedTypeIsRecognisedByItsContent(t *testing.T) {
	cases := map[string][]byte{
		"image/jpeg":      jpeg,
		"image/png":       png,
		"image/webp":      webp,
		"application/pdf": pdf,
		"video/webm":      webm,
		"video/mp4":       mp4,
		"video/quicktime": quicktime,
		"text/plain":      []byte("2026-09-24 12:00:01 ERROR handshake timeout\n\tretrying"),
	}
	for want, content := range cases {
		if got := Detect(content); got != want {
			t.Errorf("Detect(%q...) = %q, want %q", content[:8], got, want)
		}
	}
}

func TestAPhotoInAVideoContainerIsNotTakenForAVideo(t *testing.T) {
	// HEIC and AVIF share MP4's box structure. Calling one a video would put
	// a still image into a <video> that can never play it.
	if got := Detect(heic); got != "" {
		t.Errorf("HEIC detected as %q", got)
	}
}

func TestBinaryThatIsNoneOfTheAcceptedTypesIsRefused(t *testing.T) {
	for _, content := range [][]byte{
		[]byte("MZ\x90\x00\x03\x00\x00\x00"), // a Windows executable
		[]byte("PK\x03\x04\x14\x00\x00\x00"), // a zip archive
		[]byte("GIF89a\x01\x00\x01\x00"),     // not on the list
		{0x00, 0x01, 0x02, 0x03},
		{},
	} {
		if got := Detect(content); got != "" {
			t.Errorf("Detect(%q) = %q, want refusal", content, got)
		}
	}
}

func TestMarkupIsOnlyEverText(t *testing.T) {
	// It is accepted -- somebody may well attach a saved page or an SVG -- but
	// as plain text, which is only ever served as a download. Never as HTML.
	for _, content := range []string{
		`<html><script>alert(1)</script></html>`,
		`<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"/>`,
	} {
		detected := Detect([]byte(content))
		if detected != "text/plain" {
			t.Errorf("Detect(%q) = %q", content, detected)
		}
		if Inline(detected) {
			t.Errorf("%q would be shown in the page", content)
		}
	}
}

func TestTextCutOffMidCharacterIsStillText(t *testing.T) {
	// A serve-time sniff reads a fixed-size head, which can end inside a
	// Cyrillic letter. That is not binary.
	head := []byte("Ошибка подключения")
	if got := Detect(head[:len(head)-1]); got != "text/plain" {
		t.Errorf("got %q", got)
	}
}

func TestOnlyPicturesAndVideoAreShownInPlace(t *testing.T) {
	inline := []string{"image/jpeg", "image/png", "image/webp", "video/mp4", "video/webm", "video/quicktime"}
	for _, contentType := range inline {
		if !Inline(contentType) {
			t.Errorf("%s should be shown in place", contentType)
		}
	}
	for _, contentType := range []string{"application/pdf", "text/plain", "text/html", "image/svg+xml", "image/gif", ""} {
		if Inline(contentType) {
			t.Errorf("%s must be served as a download", contentType)
		}
		if Kind(contentType) != "file" {
			t.Errorf("Kind(%q) = %q, want file", contentType, Kind(contentType))
		}
	}
	if Kind("image/png") != "image" || Kind("video/quicktime") != "video" {
		t.Error("pictures and videos should be drawn as such")
	}
}

func TestEachKindHasItsOwnSizeLimit(t *testing.T) {
	if MaxBytes("video/mp4") != MaxVideoBytes || MaxBytes("image/png") != MaxImageBytes ||
		MaxBytes("application/pdf") != MaxDocumentBytes {
		t.Error("limits are not applied per kind")
	}
	// Everything a customer sends has to reach the operators' chat, and a bot
	// may not upload more than 50 MB.
	if MaxVideoBytes >= 50<<20 {
		t.Error("a video at the limit could not be forwarded to Telegram")
	}
}

// -- file names ---------------------------------------------------------------

func TestFileNamesAreCleaned(t *testing.T) {
	cases := []struct{ name, contentType, want string }{
		{`C:\Users\me\Desktop\screen.png`, "image/png", "screen.png"},
		{"../../etc/passwd", "text/plain", "passwd.txt"},
		{"setup.exe", "text/plain", "setup.exe.txt"},
		{"IMG_0042.JPG", "image/jpeg", "IMG_0042.JPG"},
		{"Скриншот ошибки.png", "image/png", "Скриншот ошибки.png"},
		{"", "video/quicktime", "file.mov"},
		{"...", "application/pdf", "file.pdf"},
		{`"quoted"<name>.pdf`, "application/pdf", "quotedname.pdf"},
		// U+202E makes "gpj.exe" display as "exe.jpg".
		{"photo\u202egpj.exe", "image/jpeg", "photogpj.exe.jpg"},
		{"line\nbreak.log", "text/plain", "linebreak.log"},
	}
	for _, c := range cases {
		if got := CleanFileName(c.name, c.contentType); got != c.want {
			t.Errorf("CleanFileName(%q, %q) = %q, want %q", c.name, c.contentType, got, c.want)
		}
	}
}

func TestALongNameKeepsItsExtension(t *testing.T) {
	name := CleanFileName(strings.Repeat("я", 300)+".mp4", "video/mp4")
	if !strings.HasSuffix(name, ".mp4") {
		t.Errorf("extension lost: %q", name)
	}
	if n := len([]rune(name)); n != maxNameRunes {
		t.Errorf("got %d runes, want %d", n, maxNameRunes)
	}
}

func TestContentDispositionCarriesACyrillicNameIntact(t *testing.T) {
	got := ContentDisposition("attachment", "лог.txt")
	want := `attachment; filename="___.txt"; filename*=UTF-8''%D0%BB%D0%BE%D0%B3.txt`
	if got != want {
		t.Errorf("got  %s\nwant %s", got, want)
	}
}

func TestContentDispositionCannotBeBrokenOutOf(t *testing.T) {
	// Operators name files from Telegram, so the name is not trusted either.
	got := ContentDisposition("inline", `a"; filename*=UTF-8''evil.html; x='.png`)
	if strings.Count(got, `"`) != 2 {
		t.Errorf("a quote escaped the filename parameter: %s", got)
	}
	_, encoded, _ := strings.Cut(got, "filename*=UTF-8''")
	if strings.ContainsAny(encoded, `"'; =`) {
		t.Errorf("the encoded name still contains a delimiter: %s", encoded)
	}
}

// -- reading a submission -----------------------------------------------------

type part struct {
	field, fileName, contentType string
	content                      []byte
}

func request(t *testing.T, limit int64, parts ...part) *http.Request {
	t.Helper()
	var body bytes.Buffer
	writer := multipart.NewWriter(&body)
	for _, p := range parts {
		header := textproto.MIMEHeader{}
		disposition := `form-data; name="` + p.field + `"`
		if p.fileName != "" || p.contentType != "" {
			disposition += `; filename="` + p.fileName + `"`
		}
		header.Set("Content-Disposition", disposition)
		if p.contentType != "" {
			header.Set("Content-Type", p.contentType)
		}
		w, err := writer.CreatePart(header)
		if err != nil {
			t.Fatal(err)
		}
		_, _ = w.Write(p.content)
	}
	_ = writer.Close()

	r := httptest.NewRequest(http.MethodPost, "/api/support/tickets", &body)
	r.Header.Set("Content-Type", writer.FormDataContentType())
	if limit > 0 {
		r.Body = http.MaxBytesReader(httptest.NewRecorder(), r.Body, limit)
	}
	return r
}

func text(field, value string) part { return part{field: field, content: []byte(value)} }

func file(name, claimed string, content []byte) part {
	return part{field: "files", fileName: name, contentType: claimed, content: content}
}

func problemCode(t *testing.T, err error) string {
	t.Helper()
	var p *Problem
	if !errors.As(err, &p) {
		t.Fatalf("expected a *Problem, got %v", err)
	}
	return p.Code
}

func TestATicketWithAFileIsRead(t *testing.T) {
	r := request(t, 0,
		text("subject", "Не подключается\r\nна iPhone"),
		text("body", "Пишет ошибку\r\n\r\nпосле обновления\x00"),
		file("screen.png", "image/png", png),
	)

	submission, err := ReadSubmission(r, true)
	if err != nil {
		t.Fatal(err)
	}
	// A title is one line: it goes into the header of a Telegram card.
	if submission.Subject != "Не подключается на iPhone" {
		t.Errorf("subject %q", submission.Subject)
	}
	if submission.Body != "Пишет ошибку\n\nпосле обновления" {
		t.Errorf("body %q", submission.Body)
	}
	if len(submission.Files) != 1 || submission.Files[0].ContentType != "image/png" ||
		submission.Files[0].Name != "screen.png" {
		t.Errorf("files %+v", submission.Files)
	}
}

func TestWhatTheBrowserClaimsAboutAFileIsIgnored(t *testing.T) {
	r := request(t, 0, text("body", "см. файл"), file("page.png", "text/html", png))
	submission, err := ReadSubmission(r, false)
	if err != nil {
		t.Fatal(err)
	}
	if got := submission.Files[0].ContentType; got != "image/png" {
		t.Errorf("stored as %q", got)
	}

	r = request(t, 0, text("body", "см. файл"), file("photo.png", "image/png", []byte("MZ\x90\x00binary")))
	if _, err := ReadSubmission(r, false); problemCode(t, err) != "unsupported_file" {
		t.Error("an executable labelled image/png was accepted")
	}
}

func TestATicketNeedsASubjectAndADescription(t *testing.T) {
	cases := map[string][]part{
		"subject_required": {text("body", "что-то сломалось")},
		"body_required":    {text("subject", "Оплата"), file("a.png", "", png)},
		"subject_too_long": {text("subject", strings.Repeat("а", MaxSubjectRunes+1)), text("body", "x")},
	}
	for want, parts := range cases {
		_, err := ReadSubmission(request(t, 0, parts...), true)
		if got := problemCode(t, err); got != want {
			t.Errorf("got %q, want %q", got, want)
		}
	}
}

func TestAFollowUpCanBeJustAFileButNotNothing(t *testing.T) {
	if _, err := ReadSubmission(request(t, 0, file("a.pdf", "", pdf)), false); err != nil {
		t.Errorf("a file on its own was refused: %v", err)
	}
	_, err := ReadSubmission(request(t, 0, text("body", "  \n\t ")), false)
	if problemCode(t, err) != "empty_message" {
		t.Error("an empty follow-up was accepted")
	}
}

func TestAFollowUpCannotSmuggleInASubject(t *testing.T) {
	_, err := ReadSubmission(request(t, 0, text("subject", "x"), text("body", "y")), false)
	if problemCode(t, err) != "bad_request" {
		t.Error("an unexpected field was accepted")
	}
}

func TestTheBodyHasALimit(t *testing.T) {
	_, err := ReadSubmission(request(t, 0,
		text("subject", "Тема"), text("body", strings.Repeat("я", MaxBodyRunes+1))), true)
	if problemCode(t, err) != "body_too_long" {
		t.Error("an overlong body was accepted")
	}
}

func TestAtMostThreeFiles(t *testing.T) {
	parts := []part{text("body", "файлы")}
	for i := 0; i <= MaxFilesPerMessage; i++ {
		parts = append(parts, file("a.png", "", png))
	}
	_, err := ReadSubmission(request(t, 0, parts...), false)
	if problemCode(t, err) != "too_many_files" {
		t.Error("a fourth file was accepted")
	}
}

func TestAnEmptyFileInputIsNotAFile(t *testing.T) {
	r := request(t, 0, text("body", "без файла"), part{field: "files", contentType: "application/octet-stream"})
	submission, err := ReadSubmission(r, false)
	if err != nil {
		t.Fatal(err)
	}
	if len(submission.Files) != 0 {
		t.Errorf("got %d files", len(submission.Files))
	}
}

func TestAPictureIsHeldToThePictureLimit(t *testing.T) {
	big := append(append([]byte{}, jpeg...), make([]byte, MaxImageBytes)...)
	_, err := ReadSubmission(request(t, 0, text("body", "фото"), file("big.jpg", "", big)), false)
	if problemCode(t, err) != "file_too_large" {
		t.Error("an oversized picture was accepted")
	}
}

func TestARequestPastTheCapIsRefusedAsTooLarge(t *testing.T) {
	r := request(t, 64, text("body", "фото"), file("a.jpg", "", append(append([]byte{}, jpeg...), make([]byte, 1024)...)))
	_, err := ReadSubmission(r, false)
	var p *Problem
	if !errors.As(err, &p) || p.Status != http.StatusRequestEntityTooLarge {
		t.Errorf("got %v", err)
	}
}

func TestNotMultipartAtAll(t *testing.T) {
	r := httptest.NewRequest(http.MethodPost, "/", strings.NewReader(`{"subject":"x"}`))
	r.Header.Set("Content-Type", "application/json")
	if _, err := ReadSubmission(r, true); problemCode(t, err) != "bad_request" {
		t.Error("a JSON body was read as a submission")
	}
}

// -- reading a stored file by range --------------------------------------------

var zeroTime time.Time

type fakeStore struct {
	data  []byte
	calls [][2]int64
}

func (f *fakeStore) fetch(_ context.Context, offset, n int64) ([]byte, error) {
	f.calls = append(f.calls, [2]int64{offset, n})
	end := min(offset+n, int64(len(f.data)))
	if offset >= end {
		return nil, nil
	}
	return f.data[offset:end], nil
}

func TestABlobReadsBackWhatWasStored(t *testing.T) {
	store := &fakeStore{data: bytes.Repeat([]byte("0123456789"), 300_000)}
	blob := NewBlob(context.Background(), int64(len(store.data)), store.fetch)

	got, err := io.ReadAll(blob)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.Equal(got, store.data) {
		t.Fatal("content differs")
	}
	// A window at a time, not a query per Read call.
	if len(store.calls) != 3 {
		t.Errorf("%d fetches for a 3 MB file", len(store.calls))
	}
}

func TestARangeCostsOnlyTheWindowsItTouches(t *testing.T) {
	store := &fakeStore{data: bytes.Repeat([]byte{7}, 40<<20)}
	blob := NewBlob(context.Background(), int64(len(store.data)), store.fetch)

	recorder := httptest.NewRecorder()
	// Set first, as the handler does. Without it ServeContent reads the start
	// of the file to guess a type -- a second fetch this request never needed.
	recorder.Header().Set("Content-Type", "video/mp4")
	r := httptest.NewRequest(http.MethodGet, "/", nil)
	r.Header.Set("Range", "bytes=30000000-30000099")
	http.ServeContent(recorder, r, "", zeroTime, blob)

	if recorder.Code != http.StatusPartialContent {
		t.Fatalf("status %d", recorder.Code)
	}
	if recorder.Body.Len() != 100 {
		t.Errorf("got %d bytes", recorder.Body.Len())
	}
	if len(store.calls) != 1 || store.calls[0][0] != 30000000 {
		t.Errorf("fetches: %v", store.calls)
	}
}

func TestAFileShorterThanRecordedIsAnErrorNotAnEnd(t *testing.T) {
	// A truncated file answered with EOF would reach the customer as a
	// complete download.
	store := &fakeStore{data: []byte("short")}
	blob := NewBlob(context.Background(), 100, store.fetch)
	_, err := io.ReadAll(blob)
	if !errors.Is(err, io.ErrUnexpectedEOF) {
		t.Errorf("got %v", err)
	}
}

func TestSeekingIsRelativeToWhereItSays(t *testing.T) {
	blob := NewBlob(context.Background(), 1000, (&fakeStore{}).fetch)
	if position, _ := blob.Seek(0, io.SeekEnd); position != 1000 {
		t.Errorf("end = %d", position)
	}
	if position, _ := blob.Seek(-10, io.SeekCurrent); position != 990 {
		t.Errorf("current = %d", position)
	}
	if _, err := blob.Seek(-1, io.SeekStart); err == nil {
		t.Error("a negative position was accepted")
	}
}
