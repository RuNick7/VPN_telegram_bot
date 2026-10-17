// Package app is vpncheck for customers: a page with one field and a few
// buttons, served to this computer alone. The same handler sits behind the
// browser tab today and behind an app window later; the check itself is the
// command line's, unchanged.
package app

import (
	"crypto/subtle"
	"embed"
	"encoding/json"
	"io"
	"io/fs"
	"net"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/check"
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

func (a *App) Handler() http.Handler {
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
	api.HandleFunc("GET /api/paste", a.handlePaste)
	api.HandleFunc("POST /api/forget", a.handleForget)

	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// A page on another site can make the browser send requests here,
		// and can point its own domain at 127.0.0.1 to get past the
		// same-origin check. Neither carries the token, and the second also
		// gives itself away in the Host it sends.
		if !localHost(r.Host) {
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
		if subtle.ConstantTimeCompare([]byte(got), []byte(a.token)) != 1 {
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
	s := state{Phase: phaseIdle, Version: a.cfg.Version, Link: a.link, Run: a.runs}
	if a.run != nil {
		a.run.view(&s)
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
		writeJSON(w, http.StatusConflict, map[string]any{"problem": &Problem{"Проверка уже идёт", "Дождитесь её конца или остановите её."}})
		return
	}
	a.start(link)
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
		return nil, "", &Problem{"Отчёта ещё нет", "Сначала дождитесь конца проверки."}
	}
	path, err := archive(r.files.Dir)
	if err != nil {
		return nil, "", &Problem{"Не удалось собрать отчёт", err.Error()}
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
		writeJSON(w, http.StatusInternalServerError, map[string]any{"problem": &Problem{"Не удалось сохранить отчёт", err.Error()}})
		return
	}
	a.update(func() { run.saved = saved })
	// The file is saved whether or not a window could show it.
	_ = a.desk.Reveal(saved)
	writeJSON(w, http.StatusOK, map[string]any{"path": saved})
}

func (a *App) handleCopy(w http.ResponseWriter, r *http.Request) {
	_, path, problem := a.report()
	if problem != nil {
		writeJSON(w, http.StatusConflict, map[string]any{"problem": problem})
		return
	}
	if err := a.desk.CopyFile(path); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]any{"problem": &Problem{
			"Не получилось скопировать файл",
			"Сохраните отчёт и перетащите файл в чат поддержки. (" + err.Error() + ")",
		}})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"name": path[strings.LastIndexAny(path, `/\`)+1:]})
}

// handlePaste reads the clipboard for the «Вставить» button, and for the
// first screen to offer a link the customer has just copied. Only a
// subscription link ever leaves this handler, never the clipboard's text.
func (a *App) handlePaste(w http.ResponseWriter, r *http.Request) {
	text, err := a.desk.ReadText()
	if err != nil {
		writeJSON(w, http.StatusOK, map[string]any{"problem": &Problem{"Буфер обмена недоступен", "Вставьте ссылку в поле сами: Cmd+V на Mac, Ctrl+V на Windows."}})
		return
	}
	link, problem := CleanLink(text, a.cfg.Domains)
	if problem != nil {
		writeJSON(w, http.StatusOK, map[string]any{"problem": &Problem{"В буфере обмена нет ссылки подписки", "Скопируйте её в боте или личном кабинете и нажмите «Вставить» ещё раз."}})
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"link": link})
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
