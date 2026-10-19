// Package app is vpncheck for customers: a page with one field and a few
// buttons, served to this computer alone. The same page is the app's window
// on macOS and Windows (WindowHandler) and a browser tab elsewhere
// (Handler); the check itself is the command line's, unchanged.
package app

import (
	"context"
	"crypto/subtle"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/report"
	"github.com/RuNick7/vpn-check/internal/site"
)

//go:embed ui
var ui embed.FS

type Config struct {
	Version string
	// Hosts a subscription link may point at (see CleanLink).
	Domains []string
	// Where runs are written, a folder each, and zipped for sending.
	Dir string
	// Where «Сохранить отчёт» puts the zip.
	Downloads string
	// Where the last link that worked is remembered; empty keeps nothing.
	LinkFile  string
	UserAgent string
	Options   check.Options
	// The website: what the subscription's status is, and where a report
	// goes. Empty leaves both out.
	Site string
	// The page is in the app's own window, which opens no links of its
	// own: the page asks the app to open them in the browser.
	Window bool
	// The system and device a report names, in place of the one Go knows
	// (the Android app names the Android version and the phone's model).
	Platform string
	// Whether the connection is charged by the megabyte, when the system
	// says so: the page then asks before measuring speed through every
	// server. Nil on a computer, where it never asks.
	Metered func() bool
}

type App struct {
	cfg   Config
	token string
	desk  desktop

	mu   sync.Mutex
	run  *run
	runs int
	link string
	seen time.Time
}

// New makes the app. token is what every API request must carry: the page
// is reachable by anything on this computer, a website open in the same
// browser included, and only the page that was handed the token may drive it.
func New(cfg Config, token string) *App {
	return &App{cfg: cfg, token: token, desk: system{}, link: readLink(cfg.LinkFile), seen: time.Now()}
}

// Stop stops a check that is running, as the «Остановить» button does.
func (a *App) Stop() {
	a.mu.Lock()
	defer a.mu.Unlock()
	if a.run != nil && a.run.active() {
		a.run.cancel()
	}
}

// Busy reports whether a check is running.
func (a *App) Busy() bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	return a.run != nil && a.run.active()
}

// Idle is how long since the page last asked anything: the page asks every
// half second while it is open, so a long silence means it was closed.
func (a *App) Idle() time.Duration {
	a.mu.Lock()
	defer a.mu.Unlock()
	return time.Since(a.seen)
}

// Handler is the page and its API over HTTP on 127.0.0.1, for a browser.
func (a *App) Handler() http.Handler { return a.handler(true) }

// WindowHandler is the same for the app's window, which asks it from
// inside this process: nothing else can reach it, so there is no address to
// check and no token to carry.
func (a *App) WindowHandler() http.Handler { return a.handler(false) }

func (a *App) handler(overHTTP bool) http.Handler {
	assets, _ := fs.Sub(ui, "ui")
	static := http.FileServerFS(assets)
	api := http.NewServeMux()
	api.HandleFunc("GET /api/state", a.handleState)
	api.HandleFunc("POST /api/check", a.handleCheck)
	api.HandleFunc("POST /api/stop", a.handleStop)
	api.HandleFunc("POST /api/reset", a.handleReset)
	api.HandleFunc("GET /api/server/{i}", a.handleServer)
	api.HandleFunc("POST /api/save", a.handleSave)
	api.HandleFunc("POST /api/copy", a.handleCopy)
	api.HandleFunc("POST /api/send", a.handleSend)
	api.HandleFunc("GET /api/paste", a.handlePaste)
	api.HandleFunc("POST /api/paste", a.handlePaste)
	api.HandleFunc("POST /api/report", a.handleReport)
	api.HandleFunc("POST /api/forget", a.handleForget)
	api.HandleFunc("POST /api/open", a.handleOpen)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// A page on another site can make the browser send requests here,
		// and can point its own domain at 127.0.0.1 to get past the
		// same-origin check. Neither carries the token, and the second also
		// gives itself away in the Host it sends.
		if overHTTP && !localHost(r.Host) {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		h := w.Header()
		h.Set("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
		h.Set("X-Content-Type-Options", "nosniff")
		h.Set("Referrer-Policy", "no-referrer")
		h.Set("Cache-Control", "no-store")
		if !strings.HasPrefix(r.URL.Path, "/api/") {
			static.ServeHTTP(w, r)
			return
		}
		got := strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer ")
		if overHTTP && subtle.ConstantTimeCompare([]byte(got), []byte(a.token)) != 1 {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		a.mu.Lock()
		a.seen = time.Now()
		a.mu.Unlock()
		api.ServeHTTP(w, r)
	})
}

func localHost(hostport string) bool {
	host, _, err := net.SplitHostPort(hostport)
	if err != nil {
		host = hostport
	}
	return host == "127.0.0.1" || host == "localhost" || host == "::1"
}

func (a *App) state() state {
	a.mu.Lock()
	defer a.mu.Unlock()
	s := state{Phase: phaseIdle, Version: a.cfg.Version, Link: a.link, Run: a.runs, Window: a.cfg.Window}
	s.Metered = a.cfg.Metered != nil && a.cfg.Metered()
	if a.run != nil {
		a.run.view(&s)
		s.CanSend = a.cfg.Site != "" && a.run.sendable()
	}
	if a.run == nil || !a.run.active() {
		// Asked afresh between runs, so the warning goes away as soon as
		// the VPN app is switched off.
		s.VPN = check.ActiveTunnel()
	}
	return s
}

func (a *App) handleState(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, a.state())
}

func (a *App) handleCheck(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Link string `json:"link"`
		// Measure speed on a metered connection; asked only there.
		Speed bool `json:"speed"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 16<<10)).Decode(&body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	link, problem := CleanLink(body.Link, a.cfg.Domains)
	if problem != nil {
		writeJSON(w, http.StatusUnprocessableEntity, map[string]any{"problem": problem})
		return
	}
	if a.Busy() {
		writeJSON(w, http.StatusConflict, map[string]any{"problem": &Problem{Title: "Проверка уже идёт", Text: "Дождитесь её конца или остановите её."}})
		return
	}
	opts := a.cfg.Options
	if a.cfg.Metered != nil && a.cfg.Metered() && !body.Speed {
		opts.SpeedBytes = 0
	}
	a.start(link, opts)
	writeJSON(w, http.StatusOK, a.state())
}

func (a *App) handleStop(w http.ResponseWriter, r *http.Request) {
	a.mu.Lock()
	if a.run != nil && a.run.active() {
		a.run.cancel()
	}
	a.mu.Unlock()
	writeJSON(w, http.StatusOK, a.state())
}

// handleReset goes back to the first screen, for another link.
func (a *App) handleReset(w http.ResponseWriter, r *http.Request) {
	a.mu.Lock()
	if a.run != nil && !a.run.active() {
		a.run = nil
	}
	a.mu.Unlock()
	writeJSON(w, http.StatusOK, a.state())
}

func (a *App) handleServer(w http.ResponseWriter, r *http.Request) {
	i, err := strconv.Atoi(r.PathValue("i"))
	a.mu.Lock()
	defer a.mu.Unlock()
	if err != nil || a.run == nil || i < 0 || i >= len(a.run.targets) {
		http.NotFound(w, r)
		return
	}
	writeJSON(w, http.StatusOK, a.run.detail(i))
}

// report is the finished run's zip, made on first use.
func (a *App) report() (*run, string, *Problem) {
	a.mu.Lock()
	r := a.run
	a.mu.Unlock()
	if r == nil || r.files == nil {
		return nil, "", &Problem{Title: "Отчёта ещё нет", Text: "Сначала дождитесь конца проверки."}
	}
	path, err := archive(r.files.Dir)
	if err != nil {
		return nil, "", &Problem{Title: "Не удалось собрать отчёт", Text: err.Error()}
	}
	return r, path, nil
}

func (a *App) handleSave(w http.ResponseWriter, r *http.Request) {
	run, path, problem := a.report()
	if problem != nil {
		writeJSON(w, http.StatusConflict, map[string]any{"problem": problem})
		return
	}
	saved, err := saveCopy(path, a.cfg.Downloads)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"problem": &Problem{Title: "Не удалось сохранить отчёт", Text: err.Error()}})
		return
	}
	a.update(func() { run.saved = saved })
	// The file is saved whether or not a window could show it.
	_ = a.desk.Reveal(saved)
	writeJSON(w, http.StatusOK, map[string]any{"path": saved})
}

// handleReport names the finished run's zip, for the Android app, which
// saves and shares it itself: the page hands the name to the app's own
// code, which finds the file in the folder it gave this process.
func (a *App) handleReport(w http.ResponseWriter, r *http.Request) {
	_, path, problem := a.report()
	if problem != nil {
		writeJSON(w, http.StatusConflict, map[string]any{"problem": problem})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"name": filepath.Base(path)})
}

func (a *App) handleCopy(w http.ResponseWriter, r *http.Request) {
	_, path, problem := a.report()
	if problem != nil {
		writeJSON(w, http.StatusConflict, map[string]any{"problem": problem})
		return
	}
	if err := a.desk.CopyFile(path); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"problem": &Problem{
			Title: "Не получилось скопировать файл",
			Text:  "Сохраните отчёт и перетащите файл в чат поддержки. (" + err.Error() + ")",
		}})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"name": path[strings.LastIndexAny(path, `/\`)+1:]})
}

// handlePaste reads the clipboard for the «Вставить» button, and for the
// first screen to offer a link the customer has just copied. Only a
// subscription link ever leaves this handler, never the clipboard's text.
// On Android the page reads the clipboard through the app and posts its
// text here instead.
func (a *App) handlePaste(w http.ResponseWriter, r *http.Request) {
	text, err := a.desk.ReadText()
	if r.Method == http.MethodPost {
		var body struct {
			Text string `json:"text"`
		}
		err = json.NewDecoder(io.LimitReader(r.Body, 16<<10)).Decode(&body)
		text = body.Text
	}
	if err != nil {
		writeJSON(w, http.StatusOK, map[string]any{"problem": &Problem{Title: "Буфер обмена недоступен", Text: "Вставьте ссылку в поле сами: Cmd+V на Mac, Ctrl+V на Windows."}})
		return
	}
	link, problem := CleanLink(text, a.cfg.Domains)
	if problem != nil {
		writeJSON(w, http.StatusOK, map[string]any{"problem": &Problem{Title: "В буфере обмена нет ссылки подписки", Text: "Скопируйте её в боте или личном кабинете и нажмите «Вставить» ещё раз."}})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"link": link})
}

// handleSend puts the report into the customer's support ticket. Pressing
// the button is the consent; the page says what goes before it is pressed.
func (a *App) handleSend(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Note string `json:"note"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 16<<10)).Decode(&body); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	a.mu.Lock()
	run := a.run
	ready := run != nil && run.files != nil && a.cfg.Site != "" && run.sendable()
	already := ready && (run.sent != nil || run.sending)
	if ready && !already {
		run.sending = true
	}
	a.mu.Unlock()
	switch {
	case !ready:
		writeJSON(w, http.StatusConflict, map[string]any{"problem": &Problem{Title: "Отправить нельзя", Text: "Сначала дождитесь конца проверки."}})
		return
	case already:
		// Once is enough: a second press, or a second tab, sends nothing.
		writeJSON(w, http.StatusOK, a.state())
		return
	}

	summary := fmt.Sprintf("Отчёт проверки серверов (vpncheck %s): %s", a.cfg.Version, run.red.String(report.OneLine(run.rep)))
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Minute)
	defer cancel()
	sent, err := site.New(a.cfg.Site).Send(ctx, run.link, summary, body.Note, run.files.Full)
	a.update(func() { run.sending, run.sent = false, sent })
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]any{"problem": sendProblem(err)})
		return
	}
	writeJSON(w, http.StatusOK, a.state())
}

// sendProblem says why a report did not go. The site answers every refusal
// in words of its own; a bare status code came from something in front of
// it, such as nginx turning a report away as too large, and is named rather
// than passed off as no answer at all.
func sendProblem(err error) *Problem {
	const fallback = " Сохраните отчёт или скопируйте файл и пришлите его в чат поддержки в Telegram."
	problem := &Problem{Title: "Не удалось отправить", Text: "Сайт поддержки не ответил." + fallback}
	var siteErr *site.Error
	switch {
	case !errors.As(err, &siteErr):
	case siteErr.Message != "":
		problem.Text = siteErr.Message
	case siteErr.Status == http.StatusRequestEntityTooLarge:
		problem.Text = "Сервер сайта не принял отчёт: он больше, чем там разрешено (HTTP 413)." + fallback
	default:
		problem.Text = fmt.Sprintf("Сайт ответил ошибкой HTTP %d.", siteErr.Status) + fallback
	}
	return problem
}

// handleOpen opens the way out of the run's problem («Продлить») in the
// browser, for the window, which opens no links itself. Only that link: the
// page names nothing, so nothing else can be opened through here.
func (a *App) handleOpen(w http.ResponseWriter, r *http.Request) {
	a.mu.Lock()
	var link string
	if a.run != nil && a.run.problem != nil {
		link = a.run.problem.Link
	}
	a.mu.Unlock()
	if !strings.HasPrefix(link, "https://") && !strings.HasPrefix(link, "http://") {
		http.NotFound(w, r)
		return
	}
	if err := a.desk.Open(link); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"problem": &Problem{Title: "Браузер не открылся", Text: "Откройте адрес сами: " + link}})
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (a *App) handleForget(w http.ResponseWriter, r *http.Request) {
	a.remember("")
	writeJSON(w, http.StatusOK, a.state())
}

// remember keeps link for the next start; empty forgets it.
func (a *App) remember(link string) {
	a.update(func() { a.link = link })
	writeLink(a.cfg.LinkFile, link)
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}
