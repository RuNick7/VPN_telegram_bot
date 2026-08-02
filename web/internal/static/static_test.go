package static

import (
	"compress/gzip"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"testing/fstest"
)

// A miniature site with one of each thing the real one has.
func testFS() fstest.MapFS {
	return fstest.MapFS{
		"index.html":            {Data: []byte("<!doctype html><title>home</title>" + strings.Repeat("x", 600))},
		"login.html":            {Data: []byte("<!doctype html><title>login</title>")},
		"auth-verify.html":      {Data: []byte("<!doctype html><title>verify</title>")},
		"gift.html":             {Data: []byte("<!doctype html><title>gift</title>")},
		"404.html":              {Data: []byte("<!doctype html><title>404</title>")},
		"app/index.html":        {Data: []byte("<!doctype html><title>app</title>")},
		"app/plans.html":        {Data: []byte("<!doctype html><title>plans</title>")},
		"app/devices.html":      {Data: []byte("<!doctype html><title>devices</title>")},
		"app/profile.html":      {Data: []byte("<!doctype html><title>profile</title>")},
		"assets/css/app.css":    {Data: []byte("body{color:#fff}" + strings.Repeat("/*pad*/", 200))},
		"assets/js/core.js":     {Data: []byte("export const x=1;" + strings.Repeat("//pad\n", 200))},
		"assets/img/logo.svg":   {Data: []byte(`<svg xmlns="http://www.w3.org/2000/svg"/>`)},
		"assets/fonts/i.woff2":  {Data: []byte("\x77\x4f\x46\x32 not really a font")},
		"assets/video/hero.mp4": {Data: []byte("\x00\x00\x00\x18ftypmp42 not really a video")},
	}
}

func newTestHandler(t *testing.T, opts Options) *Handler {
	t.Helper()
	h, err := New(testFS(), opts)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return h
}

func get(t *testing.T, h *Handler, target string, headers map[string]string) *http.Response {
	t.Helper()
	request := httptest.NewRequest(http.MethodGet, target, nil)
	for key, value := range headers {
		request.Header.Set(key, value)
	}
	recorder := httptest.NewRecorder()
	h.ServeHTTP(recorder, request)
	return recorder.Result()
}

// -- routing ---------------------------------------------------------------

func TestCleanURLsResolveToTheirPage(t *testing.T) {
	h := newTestHandler(t, Options{})

	for target, want := range map[string]string{
		"/":            "home",
		"/login":       "login",
		"/auth/verify": "verify",
		"/app":         "app",
		"/app/plans":   "plans",
		"/app/devices": "devices",
		"/app/profile": "profile",
	} {
		response := get(t, h, target, nil)
		if response.StatusCode != http.StatusOK {
			t.Errorf("%s: status %d, want 200", target, response.StatusCode)
			continue
		}
		body, _ := io.ReadAll(response.Body)
		if !strings.Contains(string(body), "<title>"+want+"</title>") {
			t.Errorf("%s served the wrong page: %s", target, body)
		}
	}
}

func TestGiftCodesAllShareOnePage(t *testing.T) {
	h := newTestHandler(t, Options{})

	for _, target := range []string{"/gift/ABC123", "/gift/very-long-code-here"} {
		response := get(t, h, target, nil)
		if response.StatusCode != http.StatusOK {
			t.Fatalf("%s: status %d, want 200", target, response.StatusCode)
		}
		body, _ := io.ReadAll(response.Body)
		if !strings.Contains(string(body), "<title>gift</title>") {
			t.Errorf("%s did not serve the gift page", target)
		}
	}

	// Without a code there is nothing to redeem, so it is not a gift page.
	if response := get(t, h, "/gift", nil); response.StatusCode != http.StatusNotFound {
		t.Errorf("/gift: status %d, want 404", response.StatusCode)
	}
}

func TestPageFilesAreNotAlsoReachableByFilename(t *testing.T) {
	// Two URLs for one page is how a site ends up with duplicates in a search
	// index, and how a "clean URL" guarantee quietly stops being one.
	h := newTestHandler(t, Options{})

	for _, target := range []string{"/index.html", "/app/index.html", "/login.html", "/404.html"} {
		if response := get(t, h, target, nil); response.StatusCode != http.StatusNotFound {
			t.Errorf("%s: status %d, want 404", target, response.StatusCode)
		}
	}
}

func TestUnknownPathsGetTheNotFoundPage(t *testing.T) {
	h := newTestHandler(t, Options{})

	response := get(t, h, "/nope", nil)
	if response.StatusCode != http.StatusNotFound {
		t.Fatalf("status %d, want 404", response.StatusCode)
	}
	body, _ := io.ReadAll(response.Body)
	if !strings.Contains(string(body), "<title>404</title>") {
		t.Error("404 did not render the designed page")
	}
	if got := response.Header.Get("Content-Type"); !strings.HasPrefix(got, "text/html") {
		t.Errorf("Content-Type %q, want text/html", got)
	}
}

func TestTrailingSlashesRedirectToTheCanonicalPath(t *testing.T) {
	h := newTestHandler(t, Options{})

	response := get(t, h, "/app/", nil)
	if response.StatusCode != http.StatusMovedPermanently {
		t.Fatalf("status %d, want 301", response.StatusCode)
	}
	if got := response.Header.Get("Location"); got != "/app" {
		t.Errorf("Location %q, want /app", got)
	}
}

func TestPathTraversalCannotEscapeTheAssetsPrefix(t *testing.T) {
	h := newTestHandler(t, Options{})

	// Everything is in a map keyed by a cleaned path, so there is no directory
	// to climb out of -- but the normalisation still has to not *create* a way
	// in by resolving a dotted path onto a page file.
	for _, target := range []string{
		"/assets/../index.html",
		"/assets/css/../../index.html",
		"/assets/%2e%2e/index.html",
		"/../index.html",
		"/assets/./css/../../app/index.html",
	} {
		response := get(t, h, target, nil)

		// Normalisation answers most of these with a redirect to the cleaned
		// path. That is only safe if the cleaned path is itself a dead end, so
		// the redirect is followed rather than accepted as a pass.
		if response.StatusCode == http.StatusMovedPermanently {
			location := response.Header.Get("Location")
			if location == target {
				t.Fatalf("%s: redirect loop", target)
			}
			response = get(t, h, location, nil)
		}

		if response.StatusCode != http.StatusNotFound {
			body, _ := io.ReadAll(response.Body)
			t.Errorf("%s: status %d, want 404. body: %s", target, response.StatusCode, body)
		}
	}
}

func TestOnlyGetAndHeadAreAllowed(t *testing.T) {
	h := newTestHandler(t, Options{})

	for _, method := range []string{http.MethodPost, http.MethodPut, http.MethodDelete} {
		request := httptest.NewRequest(method, "/", nil)
		recorder := httptest.NewRecorder()
		h.ServeHTTP(recorder, request)
		if recorder.Code != http.StatusMethodNotAllowed {
			t.Errorf("%s /: status %d, want 405", method, recorder.Code)
		}
		if got := recorder.Header().Get("Allow"); got != "GET, HEAD" {
			t.Errorf("%s /: Allow %q", method, got)
		}
	}
}

func TestHeadSendsNoBody(t *testing.T) {
	h := newTestHandler(t, Options{})

	request := httptest.NewRequest(http.MethodHead, "/", nil)
	request.Header.Set("Accept-Encoding", "gzip")
	recorder := httptest.NewRecorder()
	h.ServeHTTP(recorder, request)

	if recorder.Code != http.StatusOK {
		t.Fatalf("status %d, want 200", recorder.Code)
	}
	if recorder.Body.Len() != 0 {
		t.Errorf("HEAD returned %d bytes of body", recorder.Body.Len())
	}
}

// -- security headers ------------------------------------------------------

func TestContentSecurityPolicyForbidsInlineCodeByDefault(t *testing.T) {
	h := newTestHandler(t, Options{})
	csp := get(t, h, "/", nil).Header.Get("Content-Security-Policy")

	for _, required := range []string{
		"default-src 'none'",
		"script-src 'self'",
		"style-src 'self'",
		"base-uri 'none'",
		"frame-ancestors 'none'",
		"form-action 'self'",
	} {
		if !strings.Contains(csp, required) {
			t.Errorf("CSP is missing %q: %s", required, csp)
		}
	}
	// The whole frontend was written to avoid needing any of these. If one
	// appears, an inline script or style got added and the policy was widened
	// to accommodate it rather than the other way round.
	for _, forbidden := range []string{"unsafe-inline", "unsafe-eval", "unsafe-hashes", "*"} {
		if strings.Contains(csp, forbidden) {
			t.Errorf("CSP contains %q: %s", forbidden, csp)
		}
	}
}

func TestTelegramIsAdmittedOnlyWhenLoginIsConfigured(t *testing.T) {
	off := get(t, newTestHandler(t, Options{}), "/login", nil).
		Header.Get("Content-Security-Policy")
	if strings.Contains(off, "telegram.org") {
		t.Errorf("telegram is allowed with login off: %s", off)
	}

	on := get(t, newTestHandler(t, Options{TelegramLogin: true}), "/login", nil).
		Header.Get("Content-Security-Policy")
	if !strings.Contains(on, "script-src 'self' https://telegram.org") {
		t.Errorf("widget script not allowed: %s", on)
	}
	if !strings.Contains(on, "frame-src https://oauth.telegram.org") {
		t.Errorf("widget iframe not allowed: %s", on)
	}
}

func TestEveryResponseCarriesTheHardeningHeaders(t *testing.T) {
	h := newTestHandler(t, Options{})

	for _, target := range []string{"/", "/assets/css/app.css", "/nope"} {
		header := get(t, h, target, nil).Header
		for key, want := range map[string]string{
			"X-Content-Type-Options":       "nosniff",
			"X-Frame-Options":              "DENY",
			"Referrer-Policy":              "same-origin",
			"Cross-Origin-Opener-Policy":   "same-origin",
			"Cross-Origin-Resource-Policy": "same-origin",
		} {
			if got := header.Get(key); got != want {
				t.Errorf("%s: %s = %q, want %q", target, key, got, want)
			}
		}
		if header.Get("Permissions-Policy") == "" {
			t.Errorf("%s: no Permissions-Policy", target)
		}
	}
}

func TestHSTSOnlyOnConnectionsThatWereActuallySecure(t *testing.T) {
	h := newTestHandler(t, Options{HSTSSeconds: 31536000})

	// Sending it over plain HTTP would pin a developer's browser to HTTPS for
	// localhost, which is not undoable from the site's side.
	if got := get(t, h, "/", nil).Header.Get("Strict-Transport-Security"); got != "" {
		t.Errorf("HSTS sent over plain HTTP: %q", got)
	}

	forwarded := get(t, h, "/", map[string]string{"X-Forwarded-Proto": "https"})
	if got := forwarded.Header.Get("Strict-Transport-Security"); !strings.Contains(got, "max-age=31536000") {
		t.Errorf("HSTS behind a TLS proxy: %q", got)
	}

	off := newTestHandler(t, Options{})
	if got := get(t, off, "/", map[string]string{"X-Forwarded-Proto": "https"}).
		Header.Get("Strict-Transport-Security"); got != "" {
		t.Errorf("HSTS sent while disabled: %q", got)
	}
}

// -- caching and compression ----------------------------------------------

func TestCachePolicyMatchesHowOftenAFileCanChange(t *testing.T) {
	h := newTestHandler(t, Options{})

	cases := map[string]string{
		// Same name, same bytes, forever: replacing one means a new filename.
		"/assets/fonts/i.woff2":  "immutable",
		"/assets/img/logo.svg":   "immutable",
		"/assets/video/hero.mp4": "immutable",
		// These change under the same name on every deploy.
		"/assets/css/app.css": "max-age=600",
		"/assets/js/core.js":  "max-age=600",
		"/":                   "no-cache",
	}
	for target, want := range cases {
		got := get(t, h, target, nil).Header.Get("Cache-Control")
		if !strings.Contains(got, want) {
			t.Errorf("%s: Cache-Control %q, want it to contain %q", target, got, want)
		}
	}
}

func TestAMatchingETagAnswers304WithNoBody(t *testing.T) {
	h := newTestHandler(t, Options{})

	first := get(t, h, "/assets/css/app.css", nil)
	etag := first.Header.Get("ETag")
	if etag == "" || !strings.HasPrefix(etag, `"`) {
		t.Fatalf("no strong ETag: %q", etag)
	}

	second := get(t, h, "/assets/css/app.css", map[string]string{"If-None-Match": etag})
	if second.StatusCode != http.StatusNotModified {
		t.Fatalf("status %d, want 304", second.StatusCode)
	}
	body, _ := io.ReadAll(second.Body)
	if len(body) != 0 {
		t.Errorf("304 carried %d bytes", len(body))
	}

	// A weak validator for the same entity still matches.
	weak := get(t, h, "/assets/css/app.css", map[string]string{"If-None-Match": "W/" + etag})
	if weak.StatusCode != http.StatusNotModified {
		t.Errorf("weak comparison: status %d, want 304", weak.StatusCode)
	}
}

func TestDifferentFilesGetDifferentETags(t *testing.T) {
	h := newTestHandler(t, Options{})
	css := get(t, h, "/assets/css/app.css", nil).Header.Get("ETag")
	js := get(t, h, "/assets/js/core.js", nil).Header.Get("ETag")
	if css == js {
		t.Errorf("two files share one ETag: %s", css)
	}
}

func TestTextIsGzippedForClientsThatAskAndNotForThoseThatDont(t *testing.T) {
	h := newTestHandler(t, Options{})

	compressed := get(t, h, "/assets/css/app.css", map[string]string{"Accept-Encoding": "gzip, deflate"})
	if got := compressed.Header.Get("Content-Encoding"); got != "gzip" {
		t.Fatalf("Content-Encoding %q, want gzip", got)
	}
	reader, err := gzip.NewReader(compressed.Body)
	if err != nil {
		t.Fatalf("body is not gzip: %v", err)
	}
	body, err := io.ReadAll(reader)
	if err != nil {
		t.Fatalf("reading gzip body: %v", err)
	}
	if !strings.Contains(string(body), "body{color:#fff}") {
		t.Error("decompressed body is not the stylesheet")
	}

	plain := get(t, h, "/assets/css/app.css", nil)
	if got := plain.Header.Get("Content-Encoding"); got != "" {
		t.Errorf("Content-Encoding %q sent to a client that did not ask", got)
	}

	// Anything varying on a request header has to say so, or a shared cache
	// will hand a gzip body to a client that cannot read it.
	if got := plain.Header.Get("Vary"); !strings.Contains(got, "Accept-Encoding") {
		t.Errorf("Vary %q", got)
	}
}

func TestGzipIsRefusedWhenTheClientSaysQZero(t *testing.T) {
	h := newTestHandler(t, Options{})
	response := get(t, h, "/assets/css/app.css", map[string]string{"Accept-Encoding": "gzip;q=0"})
	if got := response.Header.Get("Content-Encoding"); got != "" {
		t.Errorf("Content-Encoding %q, want none", got)
	}
}

func TestAlreadyCompressedFilesAreNotGzippedAgain(t *testing.T) {
	h := newTestHandler(t, Options{})
	for _, target := range []string{"/assets/video/hero.mp4", "/assets/fonts/i.woff2"} {
		response := get(t, h, target, map[string]string{"Accept-Encoding": "gzip"})
		if got := response.Header.Get("Content-Encoding"); got != "" {
			t.Errorf("%s: Content-Encoding %q, want none", target, got)
		}
	}
}

func TestUncompressedBodiesSupportRangeRequests(t *testing.T) {
	// This is what lets a browser seek in the background video rather than
	// refetching the whole file.
	h := newTestHandler(t, Options{})
	response := get(t, h, "/assets/video/hero.mp4", map[string]string{"Range": "bytes=0-3"})

	if response.StatusCode != http.StatusPartialContent {
		t.Fatalf("status %d, want 206", response.StatusCode)
	}
	body, _ := io.ReadAll(response.Body)
	if len(body) != 4 {
		t.Errorf("got %d bytes, want 4", len(body))
	}
}

// -- content types ---------------------------------------------------------

func TestContentTypesAreTheOnesBrowsersRequire(t *testing.T) {
	h := newTestHandler(t, Options{})

	cases := map[string]string{
		// A module served as anything but a JavaScript type is refused
		// outright by the browser, and Windows has been known to answer
		// "text/plain" for .js out of the registry.
		"/assets/js/core.js":    "javascript",
		"/assets/css/app.css":   "text/css",
		"/assets/img/logo.svg":  "image/svg+xml",
		"/assets/fonts/i.woff2": "font/woff2",
		"/":                     "text/html",
	}
	for target, want := range cases {
		got := get(t, h, target, nil).Header.Get("Content-Type")
		if !strings.Contains(got, want) {
			t.Errorf("%s: Content-Type %q, want it to contain %q", target, got, want)
		}
	}
}

// -- icon sprite -----------------------------------------------------------

func TestTheSpriteIsInlinedIntoPages(t *testing.T) {
	// Chromium and WebKit render nothing at all for a `<use>` that points at
	// another file, and report no error while doing it. Inlining is what makes
	// the icons appear anywhere except Firefox.
	files := testFS()
	files["assets/img/icons.svg"] = &fstest.MapFile{
		Data: []byte(`<svg xmlns="http://www.w3.org/2000/svg"><symbol id="i-shield"><path d="M0 0"/></symbol></svg>`),
	}
	files["index.html"] = &fstest.MapFile{
		Data: []byte("<!doctype html><body>\n<!--icon-sprite-->\n<svg><use href=\"#i-shield\"></use></svg>"),
	}
	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	_, body := readAll(t, h, "/")
	if strings.Contains(body, "<!--icon-sprite-->") {
		t.Error("the marker survived; the sprite was not inlined")
	}
	if !strings.Contains(body, `<symbol id="i-shield">`) {
		t.Errorf("the sprite is not in the page: %s", body)
	}
	if !strings.Contains(body, `<use href="#i-shield">`) {
		t.Error("the reference was rewritten unexpectedly")
	}
}

func TestTheSpritesCommentsStayInTheSourceFile(t *testing.T) {
	// The sprite is documented at length, and those bytes would otherwise ride
	// along on every page view. The comment also quotes the external-`<use>`
	// syntax it warns against, which would read as a real reference to
	// anything scanning the served markup.
	files := testFS()
	files["assets/img/icons.svg"] = &fstest.MapFile{Data: []byte(
		"<svg xmlns=\"http://www.w3.org/2000/svg\">\n" +
			"<!-- explanation mentioning href=\"/assets/img/icons.svg#i-x\" -->\n\n" +
			"<symbol id=\"i-shield\"><path d=\"M0 0\"/></symbol>\n</svg>",
	)}
	files["index.html"] = &fstest.MapFile{
		Data: []byte("<!doctype html><body>\n<!--icon-sprite-->\n"),
	}

	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	_, body := readAll(t, h, "/")
	if strings.Contains(body, "explanation") {
		t.Error("the sprite's comments were shipped to the browser")
	}
	if strings.Contains(body, "<!--") {
		t.Errorf("a comment survived: %s", body)
	}
	if !strings.Contains(body, `<symbol id="i-shield">`) {
		t.Errorf("stripping ate the symbols: %s", body)
	}
	if strings.Contains(body, "\n\n") {
		t.Error("blank lines left behind by stripping")
	}
}

func TestAnUnterminatedCommentDoesNotEatTheSprite(t *testing.T) {
	files := testFS()
	files["assets/img/icons.svg"] = &fstest.MapFile{
		Data: []byte(`<svg><symbol id="i-shield"/></svg><!-- oops`),
	}
	files["index.html"] = &fstest.MapFile{Data: []byte("<!doctype html><body>\n<!--icon-sprite-->\n")}

	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if _, body := readAll(t, h, "/"); !strings.Contains(body, `id="i-shield"`) {
		t.Errorf("symbols lost to a malformed comment: %s", body)
	}
}

func TestPagesWithoutAMarkerAreLeftAlone(t *testing.T) {
	files := testFS()
	files["assets/img/icons.svg"] = &fstest.MapFile{Data: []byte(`<svg><symbol id="i-x"/></svg>`)}

	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if _, body := readAll(t, h, "/login"); strings.Contains(body, "<symbol") {
		t.Error("a sprite was injected into a page that did not ask for one")
	}
}

func TestAMissingSpriteDoesNotBreakStartup(t *testing.T) {
	files := testFS()
	files["index.html"] = &fstest.MapFile{Data: []byte("<!doctype html><body>\n<!--icon-sprite-->\nhi")}

	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if response, _ := readAll(t, h, "/"); response.StatusCode != http.StatusOK {
		t.Errorf("status %d, want 200", response.StatusCode)
	}
}

func readAll(t *testing.T, h *Handler, target string) (*http.Response, string) {
	t.Helper()
	response := get(t, h, target, nil)
	body, err := io.ReadAll(response.Body)
	if err != nil {
		t.Fatalf("reading %s: %v", target, err)
	}
	return response, string(body)
}

// -- start-up --------------------------------------------------------------

func TestAMissingPageFileIsNotFatal(t *testing.T) {
	// Deliberately partial: the handler must come up and serve what it has
	// rather than refuse to start over a page nobody has written yet.
	files := fstest.MapFS{"index.html": {Data: []byte("<title>home</title>")}}
	h, err := New(files, Options{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if response := get(t, h, "/", nil); response.StatusCode != http.StatusOK {
		t.Errorf("status %d, want 200", response.StatusCode)
	}
	if response := get(t, h, "/login", nil); response.StatusCode != http.StatusNotFound {
		t.Errorf("missing page: status %d, want 404", response.StatusCode)
	}
}
