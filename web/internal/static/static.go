// Package static serves the customer website.
//
// The whole site is loaded into memory at start-up: every file gets a strong
// ETag, text files get a gzip copy, and the routing table is fixed. Nothing is
// read from disk while serving, which means there is no filesystem path a
// request can influence and therefore no path-traversal surface to get wrong.
//
// It also owns the browser-facing security headers. The API sets its own on
// its own responses; these are the ones that only make sense on a document --
// the Content-Security-Policy above all, which the frontend was written to
// satisfy without a single 'unsafe-inline'.
package static

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"io/fs"
	"mime"
	"net/http"
	"path"
	"strconv"
	"strings"
	"time"
)

// Options are the few things the handler cannot work out for itself.
type Options struct {
	// TelegramLogin widens the CSP to admit Telegram's login widget. Off by
	// default: an optional button is not a reason to permanently let a third
	// party run scripts on pages that also show subscription links.
	TelegramLogin bool
	// HSTSSeconds enables Strict-Transport-Security, but only on requests that
	// actually arrived over TLS -- sending it from a plain-HTTP dev server
	// would pin the browser to HTTPS for localhost. Zero disables it.
	HSTSSeconds int
}

type asset struct {
	body         []byte
	gzipped      []byte // nil when compression was not worth it
	contentType  string
	etag         string
	cacheControl string
	modTime      time.Time
}

// Handler serves the embedded site.
type Handler struct {
	assets   map[string]*asset
	pages    map[string]*asset
	notFound *asset
	gift     *asset
	csp      string
	hsts     string
}

// pageRoutes maps a clean URL onto the file that answers it.
//
// An explicit table, rather than "look for a file whose name matches the
// path": the set of reachable URLs is then written down in one place, and a
// file appearing in the embedded tree cannot become a route by accident.
var pageRoutes = map[string]string{
	"/":                   "index.html",
	"/login":              "login.html",
	"/auth/verify":        "auth-verify.html",
	"/auth/confirm-email": "auth-confirm-email.html",
	"/app":                "app/index.html",
	"/app/plans":          "app/plans.html",
	"/app/devices":        "app/devices.html",
	"/app/profile":        "app/profile.html",

	// The agreements, hosted here rather than in a Google Doc. One URL per
	// document because that is how they are cited -- the offer references the
	// refund policy, and a payment provider asks for a link to each one, not
	// for an anchor into a page of all four.
	"/docs/offer":   "docs/offer.html",
	"/docs/refund":  "docs/refund.html",
	"/docs/terms":   "docs/terms.html",
	"/docs/privacy": "docs/privacy.html",
}

// New loads the site out of `files` and returns a handler for it.
func New(files fs.FS, opts Options) (*Handler, error) {
	h := &Handler{
		assets: make(map[string]*asset),
		pages:  make(map[string]*asset),
		csp:    buildCSP(opts.TelegramLogin),
	}
	if opts.HSTSSeconds > 0 {
		h.hsts = "max-age=" + strconv.Itoa(opts.HSTSSeconds) + "; includeSubDomains"
	}

	// Embedded files have no useful modification time, so the process start is
	// used for all of them. Correctness rests on the ETag, not on this.
	started := time.Now().UTC().Truncate(time.Second)

	sprite, _ := fs.ReadFile(files, spriteFile)

	err := fs.WalkDir(files, ".", func(name string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil || entry.IsDir() {
			return walkErr
		}
		body, err := fs.ReadFile(files, name)
		if err != nil {
			return err
		}
		if strings.HasSuffix(name, ".html") {
			body = inlineSprite(body, sprite)
		}
		h.assets["/"+name] = newAsset(body, name, started)
		return nil
	})
	if err != nil {
		return nil, err
	}

	for route, file := range pageRoutes {
		if a, ok := h.assets["/"+file]; ok {
			h.pages[route] = a
		}
	}
	h.notFound = h.assets["/404.html"]
	h.gift = h.assets["/gift.html"]
	return h, nil
}

const (
	spriteFile   = "assets/img/icons.svg"
	spriteMarker = "<!--icon-sprite-->"
)

// inlineSprite drops the icon sprite into a page in place of its marker.
//
// It has to be inlined: Chromium and WebKit do not resolve
// `<use href="external.svg#id">` at all -- the element renders as nothing, with
// no console error, so the failure is invisible until someone looks at the
// page. Firefox does resolve it, which is exactly what makes the bug easy to
// ship.
//
// Doing it here rather than in the source files keeps one copy of the sprite in
// the repository instead of nine that drift apart, and costs no request: the
// markup arrives with the page it belongs to. The substitution is a fixed
// string swap between two files we wrote, so there is no input to escape.
func inlineSprite(page, sprite []byte) []byte {
	if len(sprite) == 0 {
		return page
	}
	return bytes.Replace(page, []byte(spriteMarker), stripComments(sprite), 1)
}

// stripComments removes XML/HTML comments and the blank lines they leave.
//
// The sprite file is heavily commented, and without this every one of those
// bytes would be shipped on every page view. It also keeps the explanation of
// *why* the sprite is inlined -- which necessarily quotes the external-`<use>`
// syntax it is warning about -- from reading as a real reference to a page
// that scans the served markup.
func stripComments(source []byte) []byte {
	out := make([]byte, 0, len(source))
	rest := source
	for {
		start := bytes.Index(rest, []byte("<!--"))
		if start < 0 {
			out = append(out, rest...)
			break
		}
		end := bytes.Index(rest[start:], []byte("-->"))
		if end < 0 {
			// Unterminated: keep it rather than silently eating the remainder
			// of the sprite.
			out = append(out, rest...)
			break
		}
		out = append(out, rest[:start]...)
		rest = rest[start+end+len("-->"):]
	}

	lines := bytes.Split(out, []byte("\n"))
	kept := lines[:0]
	for _, line := range lines {
		if len(bytes.TrimSpace(line)) > 0 {
			kept = append(kept, line)
		}
	}
	return bytes.Join(kept, []byte("\n"))
}

// buildCSP writes the policy the frontend was built to satisfy.
//
// `default-src 'none'` with everything else named explicitly, and no
// 'unsafe-inline' in either script-src or style-src -- which is why there is
// not one inline <script>, one inline <style>, or one `style=` attribute
// anywhere in the site. `base-uri 'none'` and `frame-ancestors 'none'` close
// the two ways a page can be subverted without executing any script of its
// own: retargeting every relative URL, and being framed by somebody else.
func buildCSP(telegramLogin bool) string {
	script := "'self'"
	frame := "'none'"
	if telegramLogin {
		// The widget is one script from telegram.org that opens an iframe on
		// oauth.telegram.org. Redirect mode is used rather than the callback
		// form precisely so 'unsafe-eval' is not needed alongside this.
		script = "'self' https://telegram.org"
		frame = "https://oauth.telegram.org"
	}
	return strings.Join([]string{
		"default-src 'none'",
		"script-src " + script,
		"style-src 'self'",
		"img-src 'self'",
		"font-src 'self'",
		"media-src 'self'",
		"connect-src 'self'",
		"frame-src " + frame,
		"form-action 'self'",
		"base-uri 'none'",
		"frame-ancestors 'none'",
	}, "; ")
}

// -- assets ---------------------------------------------------------------

func newAsset(body []byte, name string, modTime time.Time) *asset {
	sum := sha256.Sum256(body)
	a := &asset{
		body:         body,
		contentType:  contentTypeFor(name),
		etag:         `"` + hex.EncodeToString(sum[:12]) + `"`,
		cacheControl: cachePolicyFor(name),
		modTime:      modTime,
	}
	if compressible(a.contentType) {
		if squeezed := squeeze(body); squeezed != nil {
			a.gzipped = squeezed
		}
	}
	return a
}

// ourTypes is the authoritative table for everything this site serves.
//
// Consulted before the platform's, not after, because the platform's answer is
// not the same everywhere: Windows reads the registry, and the Alpine image
// this ships in has no /etc/mime.types at all, so `mime.TypeByExtension` there
// returns nothing for perfectly ordinary extensions. That asymmetry is how a
// video went out as application/octet-stream from a container while testing
// clean on a developer's machine.
var ourTypes = map[string]string{
	".html":  "text/html; charset=utf-8",
	".css":   "text/css; charset=utf-8",
	".js":    "text/javascript; charset=utf-8",
	".mjs":   "text/javascript; charset=utf-8",
	".json":  "application/json; charset=utf-8",
	".svg":   "image/svg+xml",
	".png":   "image/png",
	".webp":  "image/webp",
	".avif":  "image/avif",
	".ico":   "image/x-icon",
	".woff2": "font/woff2",
	".mp4":   "video/mp4",
	".webm":  "video/webm",
	".txt":   "text/plain; charset=utf-8",
	".xml":   "application/xml",
}

func contentTypeFor(name string) string {
	if ct, ok := ourTypes[strings.ToLower(path.Ext(name))]; ok {
		return ct
	}
	if ct := mime.TypeByExtension(path.Ext(name)); ct != "" {
		return ct
	}
	return "application/octet-stream"
}

// cachePolicyFor decides how long a browser may keep a file.
//
// Fonts, images and video are cached for a year: their content is fixed for a
// given name, and changing one means shipping a new name.
//
// HTML, CSS and JavaScript all revalidate. They change on every deploy *under
// the same name*, and the three have to move together -- markup that expects
// new script behaviour paired with a cached old script is a broken page, not a
// slightly stale one. A `max-age` here bought one saved round trip and cost
// exactly that: after a deploy, returning visitors ran the previous
// JavaScript against the current markup for as long as the age lasted, with no
// way to tell from the outside. Revalidation is cheap -- a matching ETag
// answers 304 with no body -- and the whole site is about 30 KB.
//
// `no-store` is deliberately not used: none of this is secret, and a 304 still
// saves the transfer.
func cachePolicyFor(name string) string {
	switch {
	case strings.HasPrefix(name, "assets/fonts/"),
		strings.HasPrefix(name, "assets/img/"),
		strings.HasPrefix(name, "assets/video/"):
		return "public, max-age=31536000, immutable"
	default:
		return "no-cache"
	}
}

func compressible(contentType string) bool {
	return strings.HasPrefix(contentType, "text/") ||
		strings.HasPrefix(contentType, "image/svg") ||
		strings.Contains(contentType, "javascript") ||
		strings.Contains(contentType, "json")
}

// squeeze gzips a body, or returns nil if the result is not worth serving.
//
// Compressing something that barely shrinks costs CPU on both ends and gives
// up Range support for nothing.
func squeeze(body []byte) []byte {
	if len(body) < 512 {
		return nil
	}
	var buf bytes.Buffer
	writer, err := gzip.NewWriterLevel(&buf, gzip.BestCompression)
	if err != nil {
		return nil
	}
	if _, err := writer.Write(body); err != nil {
		return nil
	}
	if err := writer.Close(); err != nil {
		return nil
	}
	if buf.Len() >= len(body)*9/10 {
		return nil
	}
	return buf.Bytes()
}

// -- serving --------------------------------------------------------------

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	h.setSecurityHeaders(w, r)

	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		w.Header().Set("Allow", "GET, HEAD")
		h.serveStatus(w, r, http.StatusMethodNotAllowed)
		return
	}

	// Normalising first means `/app/../assets/x` and `//assets//x` resolve to
	// one canonical URL before anything is looked up, and that the URL in the
	// address bar is the one the cache is keyed on.
	cleaned := path.Clean(r.URL.Path)
	if cleaned != "/" {
		cleaned = strings.TrimSuffix(cleaned, "/")
	}
	if cleaned == "" {
		cleaned = "/"
	}
	if cleaned != r.URL.Path {
		target := *r.URL
		target.Path = cleaned
		http.Redirect(w, r, target.RequestURI(), http.StatusMovedPermanently)
		return
	}

	if page, ok := h.pages[cleaned]; ok {
		h.serve(w, r, page, http.StatusOK)
		return
	}

	// `/gift/<code>` is one page for many URLs: the code is read from the path
	// by the script, so the server does not have to know or log it.
	if h.gift != nil && strings.HasPrefix(cleaned, "/gift/") && len(cleaned) > len("/gift/") {
		h.serve(w, r, h.gift, http.StatusOK)
		return
	}

	// Only /assets/ is reachable by filename. Serving the whole tree that way
	// would also expose the page files under a second set of URLs, which is
	// how a "clean URL" site ends up with two of everything in a search index.
	if strings.HasPrefix(cleaned, "/assets/") {
		if a, ok := h.assets[cleaned]; ok {
			h.serve(w, r, a, http.StatusOK)
			return
		}
	}

	h.serveStatus(w, r, http.StatusNotFound)
}

func (h *Handler) setSecurityHeaders(w http.ResponseWriter, r *http.Request) {
	header := w.Header()
	header.Set("Content-Security-Policy", h.csp)
	header.Set("X-Content-Type-Options", "nosniff")
	header.Set("X-Frame-Options", "DENY")
	// same-origin, not no-referrer: URLs on this site carry gift codes and
	// sign-in tokens, and nothing outside it needs to know where a visitor
	// came from.
	header.Set("Referrer-Policy", "same-origin")
	header.Set("Cross-Origin-Opener-Policy", "same-origin")
	header.Set("Cross-Origin-Resource-Policy", "same-origin")
	header.Set("Permissions-Policy",
		"accelerometer=(), autoplay=(self), camera=(), display-capture=(), "+
			"geolocation=(), gyroscope=(), magnetometer=(), microphone=(), "+
			"payment=(), usb=()")

	if h.hsts != "" && isSecure(r) {
		header.Set("Strict-Transport-Security", h.hsts)
	}
}

// isSecure reports whether the request reached the user over TLS.
//
// X-Forwarded-Proto is only meaningful because this process is expected to
// listen on loopback behind our own terminator. It decides one thing -- whether
// to send HSTS -- and authorises nothing.
func isSecure(r *http.Request) bool {
	if r.TLS != nil {
		return true
	}
	return strings.EqualFold(r.Header.Get("X-Forwarded-Proto"), "https")
}

func (h *Handler) serveStatus(w http.ResponseWriter, r *http.Request, status int) {
	if h.notFound == nil {
		http.Error(w, http.StatusText(status), status)
		return
	}
	h.serve(w, r, h.notFound, status)
}

func (h *Handler) serve(w http.ResponseWriter, r *http.Request, a *asset, status int) {
	header := w.Header()
	header.Set("Content-Type", a.contentType)
	header.Set("Cache-Control", a.cacheControl)
	header.Set("ETag", a.etag)
	header.Set("Vary", "Accept-Encoding")

	if status == http.StatusOK && matchesETag(r.Header.Get("If-None-Match"), a.etag) {
		w.WriteHeader(http.StatusNotModified)
		return
	}

	body := a.body
	if a.gzipped != nil && acceptsGzip(r) {
		body = a.gzipped
		header.Set("Content-Encoding", "gzip")
	} else if status == http.StatusOK {
		// Uncompressed bodies are served through ServeContent so that byte
		// ranges work -- which is what lets a browser seek in the background
		// video instead of refetching it.
		header.Set("Content-Type", a.contentType)
		http.ServeContent(w, r, "", a.modTime, bytes.NewReader(body))
		return
	}

	header.Set("Content-Length", strconv.Itoa(len(body)))
	w.WriteHeader(status)
	if r.Method != http.MethodHead {
		_, _ = w.Write(body)
	}
}

func acceptsGzip(r *http.Request) bool {
	for _, part := range strings.Split(r.Header.Get("Accept-Encoding"), ",") {
		name, params, _ := strings.Cut(strings.TrimSpace(part), ";")
		if !strings.EqualFold(strings.TrimSpace(name), "gzip") {
			continue
		}
		// `gzip;q=0` is a client saying explicitly that it does not want it.
		return !strings.Contains(strings.ReplaceAll(params, " ", ""), "q=0")
	}
	return false
}

// matchesETag implements the If-None-Match comparison, including `*` and the
// weak-comparison rule that ignores a `W/` prefix.
func matchesETag(header, etag string) bool {
	if header == "" {
		return false
	}
	if strings.TrimSpace(header) == "*" {
		return true
	}
	for _, candidate := range strings.Split(header, ",") {
		candidate = strings.TrimSpace(candidate)
		candidate = strings.TrimPrefix(candidate, "W/")
		if candidate == etag {
			return true
		}
	}
	return false
}
