package support

import (
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"strings"
	"unicode"
	"unicode/utf8"
)

// Submission is one message as the customer sent it, already checked.
type Submission struct {
	Subject string
	Body    string
	Files   []File
}

// File is one accepted attachment. ContentType is what Detect found, never
// what the browser claimed.
type File struct {
	Name        string
	ContentType string
	Data        []byte
}

// Bytes is the combined size of the files.
func (s *Submission) Bytes() int64 {
	var total int64
	for _, file := range s.Files {
		total += int64(len(file.Data))
	}
	return total
}

// Problem is a submission refused for something the customer can fix. The
// message is written for them and is safe to show as is.
type Problem struct {
	Status  int
	Code    string
	Message string
}

func (p *Problem) Error() string { return p.Code + ": " + p.Message }

func problem(status int, code, message string) *Problem {
	return &Problem{Status: status, Code: code, Message: message}
}

var errTooLarge = problem(http.StatusRequestEntityTooLarge, "too_large",
	fmt.Sprintf("Слишком много: все файлы сообщения вместе — не больше %d МБ.", MaxMessageBytes>>20))

// AcceptedHint names what may be attached, for the messages that refuse
// something else.
const AcceptedHint = "Можно приложить фото (JPG, PNG, WebP), видео (MP4, MOV, WebM), PDF или текстовый файл."

// ReadSubmission reads a multipart/form-data message: `subject` (only when
// wantSubject), `body`, and up to MaxFilesPerMessage parts named `files`.
//
// It streams rather than calling ParseMultipartForm, which would spool the
// whole request to a temporary file before a single limit could be applied.
// Here each limit bites while reading: an oversized file is cut off at the
// limit rather than read to the end and refused afterwards. The caller is
// expected to have wrapped the body in http.MaxBytesReader as well, which is
// what bounds the request as a whole.
//
// Anything the customer can fix comes back as a *Problem.
func ReadSubmission(r *http.Request, wantSubject bool) (*Submission, error) {
	reader, err := r.MultipartReader()
	if err != nil {
		return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
	}

	var submission Submission
	var total int64
	seen := map[string]bool{}
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, readProblem(err)
		}

		name := part.FormName()
		switch {
		case name == "subject" && wantSubject, name == "body":
			if seen[name] {
				return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
			}
			seen[name] = true
			// Runes can be four bytes each; the rune count is checked once
			// the text is normalised.
			limit := MaxBodyRunes
			if name == "subject" {
				limit = MaxSubjectRunes
			}
			text, err := readText(part, int64(limit)*utf8.UTFMax)
			if err != nil {
				return nil, err
			}
			if name == "subject" {
				submission.Subject = text
			} else {
				submission.Body = text
			}

		case name == "files":
			if part.FileName() == "" {
				// An empty file input still sends a part; it is not a file.
				_, _ = io.Copy(io.Discard, part)
				continue
			}
			if len(submission.Files) == MaxFilesPerMessage {
				return nil, problem(http.StatusBadRequest, "too_many_files",
					fmt.Sprintf("Можно приложить не больше %d файлов.", MaxFilesPerMessage))
			}
			file, err := readFile(part)
			if err != nil {
				return nil, err
			}
			total += int64(len(file.Data))
			if total > MaxMessageBytes {
				return nil, errTooLarge
			}
			submission.Files = append(submission.Files, *file)

		default:
			// Refused rather than ignored, as the JSON endpoints refuse
			// unknown fields: a request this code was not written for is not
			// one to half-honour.
			return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		}
	}

	submission.Subject = normalizeSubject(submission.Subject)
	submission.Body = normalizeBody(submission.Body)
	if err := validate(&submission, wantSubject); err != nil {
		return nil, err
	}
	return &submission, nil
}

func validate(s *Submission, wantSubject bool) error {
	if wantSubject {
		switch length := utf8.RuneCountInString(s.Subject); {
		case length < 3:
			return problem(http.StatusBadRequest, "subject_required", "Коротко опишите тему обращения.")
		case length > MaxSubjectRunes:
			return problem(http.StatusBadRequest, "subject_too_long",
				fmt.Sprintf("Тема — не длиннее %d символов.", MaxSubjectRunes))
		}
		if s.Body == "" {
			return problem(http.StatusBadRequest, "body_required", "Опишите, что случилось.")
		}
	}
	if s.Body == "" && len(s.Files) == 0 {
		return problem(http.StatusBadRequest, "empty_message", "Напишите сообщение или приложите файл.")
	}
	if utf8.RuneCountInString(s.Body) > MaxBodyRunes {
		return problem(http.StatusBadRequest, "body_too_long",
			fmt.Sprintf("Сообщение — не длиннее %d символов.", MaxBodyRunes))
	}
	return nil
}

func readText(part *multipart.Part, maxBytes int64) (string, error) {
	raw, err := io.ReadAll(io.LimitReader(part, maxBytes+1))
	if err != nil {
		return "", readProblem(err)
	}
	if int64(len(raw)) > maxBytes {
		return "", problem(http.StatusBadRequest, "too_long", "Слишком длинный текст.")
	}
	return strings.ToValidUTF8(string(raw), "�"), nil
}

func readFile(part *multipart.Part) (*File, error) {
	// Read to the largest any type may be, then hold the file to its own
	// type's limit once the type is known.
	data, err := io.ReadAll(io.LimitReader(part, MaxVideoBytes+1))
	if err != nil {
		return nil, readProblem(err)
	}
	original := CleanFileName(part.FileName(), "")
	if len(data) == 0 {
		return nil, problem(http.StatusBadRequest, "empty_file",
			fmt.Sprintf("Файл «%s» пустой.", original))
	}

	contentType := Detect(data)
	if contentType == "" {
		return nil, problem(http.StatusUnsupportedMediaType, "unsupported_file",
			fmt.Sprintf("Файл «%s» не подходит. %s", original, AcceptedHint))
	}
	if limit := MaxBytes(contentType); int64(len(data)) > limit {
		return nil, problem(http.StatusRequestEntityTooLarge, "file_too_large",
			fmt.Sprintf("Файл «%s» больше %d МБ.", original, limit>>20))
	}
	return &File{
		Name:        CleanFileName(part.FileName(), contentType),
		ContentType: contentType,
		Data:        data,
	}, nil
}

// readProblem says what went wrong while reading the request. Past the size
// cap it is the customer's upload that is too big; anything else is a
// request broken in transit, most often a connection that dropped mid-upload.
func readProblem(err error) error {
	var tooLarge *http.MaxBytesError
	if errors.As(err, &tooLarge) {
		return errTooLarge
	}
	return problem(http.StatusBadRequest, "upload_interrupted",
		"Загрузка прервалась. Проверьте подключение и отправьте ещё раз.")
}

// normalizeSubject makes the subject one line: it is a title, it goes into
// a Telegram card's header, and a newline there would break the card apart.
func normalizeSubject(subject string) string {
	return strings.Join(strings.FieldsFunc(subject, func(r rune) bool {
		return unicode.IsSpace(r) || unicode.IsControl(r)
	}), " ")
}

// normalizeBody keeps the customer's line breaks and tabs and nothing else
// invisible: Windows line endings become plain ones, and other control
// characters -- which would come out as garbage in the operators' chat --
// are dropped.
func normalizeBody(body string) string {
	body = strings.ReplaceAll(body, "\r\n", "\n")
	body = strings.Map(func(r rune) rune {
		if r == '\n' || r == '\t' {
			return r
		}
		if unicode.IsControl(r) {
			return -1
		}
		return r
	}, body)
	return strings.TrimSpace(body)
}
