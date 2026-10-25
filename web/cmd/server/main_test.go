package main

import (
	"encoding/json"
	"io"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/frontend"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/static"
)

// -- routing composition ---------------------------------------------------

func TestTheAPIOwnsItsPathsAndTheSiteOwnsTheRest(t *testing.T) {
	apiHandler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, "api")
	})
	site := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, "site")
	})
	auto := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = io.WriteString(w, "auto")
	})
	handler := routes(apiHandler, site, auto)

	cases := map[string]string{
		"/api/health":          "api",
		"/api/me":              "api",
		"/api/payments/abc":    "api",
		"/auth/telegram":       "api",
		"/":                    "site",
		"/login":               "site",
		"/auth/verify":         "site",
		"/app/devices":         "site",
		"/gift/ABC":            "site",
		"/assets/css/app.css":  "site",
		"/apifoo":              "site", // not a prefix match on /api/
		"/auth/telegram/extra": "site",
		// Both spellings, because a phone that answers 301 before the app
		// scheme is a round trip on a link somebody is standing there tapping.
		"/auto":    "auto",
		"/auto/":   "auto",
		"/autofoo": "site", // not a prefix match on /auto either
	}
	for target, want := range cases {
		recorder := httptest.NewRecorder()
		handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, target, nil))
		if got := recorder.Body.String(); got != want {
			t.Errorf("%s went to %q, want %q", target, got, want)
		}
	}
}

// -- the real embedded site ------------------------------------------------

// newRealSite builds the handler over the actual embedded frontend, which is
// what makes the tests below catch a file that was renamed, deleted, or never
// added to the embed patterns.
func newRealSite(t *testing.T) http.Handler {
	t.Helper()
	site, err := static.New(frontend.Files, static.Options{TelegramLogin: true, HSTSSeconds: 31536000})
	if err != nil {
		t.Fatalf("loading the embedded frontend: %v", err)
	}
	return site
}

func fetch(t *testing.T, handler http.Handler, target string) (*http.Response, string) {
	t.Helper()
	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, target, nil))
	response := recorder.Result()
	body, _ := io.ReadAll(response.Body)
	return response, string(body)
}

func TestEveryPageCarriesTheSharedFooter(t *testing.T) {
	// Every page, including the ones somebody lands on when something has gone
	// wrong: a 404 and the two token-redeeming pages are exactly where a
	// visitor needs the documents and a way to reach support, and they are also
	// the pages easiest to forget.
	site := newRealSite(t)
	targets := append(static.PageRoutes(), "/gift/X", "/no-such-page")

	for _, target := range targets {
		_, body := fetch(t, site, target)

		if !strings.Contains(body, `<footer class="site-footer`) {
			t.Errorf("%s has no footer", target)
			continue
		}
		for _, doc := range []string{"license", "privacy"} {
			if !strings.Contains(body, `data-doc="`+doc+`"`) {
				t.Errorf("%s: footer is missing the %s link", target, doc)
			}
		}
		if !strings.Contains(body, "data-support") {
			t.Errorf("%s: footer offers no way to reach support", target)
		}
		// Without the module the support link stays hidden and the document
		// links stop following configuration.
		if !strings.Contains(body, "/assets/js/footer.js") {
			t.Errorf("%s does not load footer.js", target)
		}
	}
}

func TestACabinetPageGivesItsFooterRoomForTheTabBar(t *testing.T) {
	// The tab bar is fixed over the bottom of the viewport on phones. A footer
	// without the modifier that clears it is readable everywhere except the
	// last two lines, on the only screen size where the bar exists.
	site := newRealSite(t)
	for _, target := range static.PageRoutes() {
		_, body := fetch(t, site, target)
		if !strings.Contains(body, `class="tabbar"`) {
			continue
		}
		if !strings.Contains(body, `<footer class="site-footer app-footer"`) {
			t.Errorf("%s has a tab bar but its footer does not clear it", target)
		}
	}
}

func TestEveryRouteOfTheRealSiteRenders(t *testing.T) {
	site := newRealSite(t)

	// The real route table, not a copy of it. A hand-written list here is how
	// four document pages shipped 404ing: they were added to pageRoutes and to
	// the embed patterns separately, one was forgotten, and a route with no
	// file behind it is simply never registered.
	for _, target := range append(static.PageRoutes(), "/gift/TESTCODE") {
		response, body := fetch(t, site, target)
		if response.StatusCode != http.StatusOK {
			t.Errorf("%s: status %d", target, response.StatusCode)
			continue
		}
		if !strings.Contains(body, "<!doctype html>") {
			t.Errorf("%s does not look like a page", target)
		}
		if !strings.Contains(body, `lang="ru"`) {
			t.Errorf("%s has no language set", target)
		}
	}
}

func TestEveryAssetThePagesReferenceExists(t *testing.T) {
	// A missing stylesheet or module is invisible in Go's tests otherwise: the
	// page still returns 200 and the site is simply broken in the browser.
	site := newRealSite(t)
	pages := append(static.PageRoutes(), "/gift/X")

	seen := map[string]bool{}
	for _, page := range pages {
		_, body := fetch(t, site, page)
		for _, reference := range extractAssetPaths(body) {
			if seen[reference] {
				continue
			}
			seen[reference] = true
			response, _ := fetch(t, site, reference)
			if response.StatusCode != http.StatusOK {
				t.Errorf("%s references %s, which returns %d", page, reference, response.StatusCode)
			}
		}
	}
	if len(seen) < 8 {
		t.Errorf("only found %d asset references; the extractor is probably broken", len(seen))
	}
}

// extractAssetPaths pulls every "/assets/..." out of an HTML document.
func extractAssetPaths(body string) []string {
	var found []string
	rest := body
	for {
		index := strings.Index(rest, `"/assets/`)
		if index < 0 {
			return found
		}
		rest = rest[index+1:]
		end := strings.IndexByte(rest, '"')
		if end < 0 {
			return found
		}
		// Fragments address a symbol inside the icon sprite, not a file.
		path, _, _ := strings.Cut(rest[:end], "#")
		found = append(found, path)
		rest = rest[end:]
	}
}

func TestTheFrontendContainsNoInlineScriptOrStyle(t *testing.T) {
	// The Content-Security-Policy has no 'unsafe-inline' in it, so an inline
	// block would simply not run -- silently, and only in production. This is
	// the check that keeps the markup and the policy honest about each other.
	site := newRealSite(t)

	for _, page := range []string{
		"/", "/login", "/auth/verify", "/app", "/app/plans",
		"/app/devices", "/app/profile", "/app/support", "/gift/X",
	} {
		_, body := fetch(t, site, page)

		if strings.Contains(body, "<style") {
			t.Errorf("%s has an inline <style> block", page)
		}
		if strings.Contains(body, " style=") {
			t.Errorf("%s has an inline style attribute", page)
		}
		// A <script> is fine only as a src= reference with no body of its own.
		for _, fragment := range strings.Split(body, "<script")[1:] {
			tag, after, _ := strings.Cut(fragment, ">")
			if !strings.Contains(tag, "src=") {
				t.Errorf("%s has a <script> with no src: <script%s>", page, tag)
			}
			if inner, _, ok := strings.Cut(after, "</script>"); ok && strings.TrimSpace(inner) != "" {
				t.Errorf("%s has script content inline: %q", page, strings.TrimSpace(inner))
			}
		}
		for _, handler := range []string{" onclick=", " onload=", " onerror=", " onsubmit="} {
			if strings.Contains(body, handler) {
				t.Errorf("%s uses an inline %s handler", page, strings.TrimSpace(handler))
			}
		}
	}
}

func TestSignedInPagesAreNotIndexable(t *testing.T) {
	// A cabinet page in a search index is not a leak on its own -- they need a
	// session -- but /gift/<code> and /auth/verify carry live credentials in
	// the URL, and a crawler following one spends it.
	site := newRealSite(t)

	for _, page := range []string{
		"/login", "/auth/verify", "/app", "/app/plans",
		"/app/devices", "/app/profile", "/app/support", "/gift/X",
	} {
		_, body := fetch(t, site, page)
		if !strings.Contains(body, `name="robots"`) || !strings.Contains(body, "noindex") {
			t.Errorf("%s is missing a noindex directive", page)
		}
	}

	// The landing page is the one that should be found.
	_, home := fetch(t, site, "/")
	if strings.Contains(home, "noindex") {
		t.Error("the landing page is marked noindex")
	}
}

func TestCredentialBearingPagesSendNoReferrer(t *testing.T) {
	// The token and the gift code are in the URL on these two. Any resource
	// they load would otherwise carry it in a Referer header.
	site := newRealSite(t)

	for _, page := range []string{"/auth/verify", "/gift/X"} {
		_, body := fetch(t, site, page)
		if !strings.Contains(body, `name="referrer" content="no-referrer"`) {
			t.Errorf("%s does not suppress the referrer", page)
		}
	}
}

func TestFontsAreServedFromThisOriginOnly(t *testing.T) {
	// The whole point of self-hosting: a customer whose network cannot reach
	// Google still gets the typeface, and the icons stay icons instead of
	// turning into the words "person" and "devices".
	site := newRealSite(t)

	for _, page := range []string{"/", "/login", "/app"} {
		_, body := fetch(t, site, page)
		for _, host := range []string{"fonts.googleapis.com", "fonts.gstatic.com", "cdn.tailwindcss.com"} {
			if strings.Contains(body, host) {
				t.Errorf("%s still loads from %s", page, host)
			}
		}
	}

	response, css := fetch(t, site, "/assets/css/app.css")
	if response.StatusCode != http.StatusOK {
		t.Fatalf("stylesheet: status %d", response.StatusCode)
	}
	if strings.Contains(css, "https://") {
		t.Error("the stylesheet references an external origin")
	}

	for _, font := range []string{
		"/assets/fonts/inter-cyrillic.woff2",
		"/assets/fonts/inter-latin.woff2",
		"/assets/fonts/jetbrains-mono-cyrillic.woff2",
		"/assets/fonts/jetbrains-mono-latin.woff2",
	} {
		if response, _ := fetch(t, site, font); response.StatusCode != http.StatusOK {
			t.Errorf("%s: status %d", font, response.StatusCode)
		}
	}
}

func TestTheHeroHasEveryFormatItPromises(t *testing.T) {
	// landing.js offers three codecs and a poster. A missing one is a black
	// rectangle for whichever browsers needed exactly that file.
	site := newRealSite(t)

	for _, asset := range []string{
		"/assets/video/hero.av1.mp4",
		"/assets/video/hero.webm",
		"/assets/video/hero.mp4",
		"/assets/img/hero-poster.avif",
		"/assets/img/hero-poster.webp",
	} {
		response, _ := fetch(t, site, asset)
		if response.StatusCode != http.StatusOK {
			t.Errorf("%s: status %d", asset, response.StatusCode)
		}
	}
}

func TestNoPageStillPointsAtTheSpriteAsAnExternalFile(t *testing.T) {
	// `<use href="icons.svg#id">` renders as nothing in Chromium and WebKit,
	// with no error logged -- and works in Firefox, which is what makes it easy
	// to ship. Every reference has to be a bare fragment into the inlined copy.
	site := newRealSite(t)

	for _, page := range []string{
		"/", "/login", "/auth/verify", "/app", "/app/plans",
		"/app/devices", "/app/profile", "/gift/X", "/nope",
	} {
		_, body := fetch(t, site, page)

		// The sprite carries a comment explaining this, which mentions the
		// path; only a real `href=` to it is a bug.
		if strings.Contains(body, `href="/assets/img/icons.svg#`) {
			t.Errorf("%s references the sprite as an external file", page)
		}
		if strings.Contains(body, "<!--icon-sprite-->") {
			t.Errorf("%s still has the marker: the sprite was not inlined", page)
		}
		if !strings.Contains(body, `id="i-shield"`) {
			t.Errorf("%s has no inlined sprite", page)
		}
	}
}

func TestNoRealAssetIsServedAsAnUnknownType(t *testing.T) {
	// application/octet-stream is what the handler falls back to when it does
	// not recognise an extension, and it is a real failure: a browser will not
	// run a module, apply a stylesheet or decode a video it is handed under
	// that type. Walking the embedded tree rather than a list means a new kind
	// of asset cannot be added without either being recognised or failing here.
	//
	// This is also platform-dependent in a way that hides it: the fallback
	// consults the operating system's mime database, which is populated on a
	// developer's machine and empty in the Alpine image this ships in.
	site := newRealSite(t)

	checked := 0
	err := fs.WalkDir(frontend.Files, "assets", func(name string, entry fs.DirEntry, walkErr error) error {
		if walkErr != nil || entry.IsDir() {
			return walkErr
		}
		response, _ := fetch(t, site, "/"+name)
		if response.StatusCode != http.StatusOK {
			t.Errorf("%s: status %d", name, response.StatusCode)
			return nil
		}
		if got := response.Header.Get("Content-Type"); strings.HasPrefix(got, "application/octet-stream") {
			t.Errorf("%s is served as %q", name, got)
		}
		checked++
		return nil
	})
	if err != nil {
		t.Fatal(err)
	}
	if checked < 20 {
		t.Errorf("only checked %d assets; the walk is probably wrong", checked)
	}
}

func TestEveryIconTheSiteAsksForIsInTheSprite(t *testing.T) {
	site := newRealSite(t)

	_, sprite := fetch(t, site, "/assets/img/icons.svg")
	pages := append(static.PageRoutes(), "/gift/X")

	checked := 0
	for _, page := range pages {
		_, body := fetch(t, site, page)
		for _, name := range append(spriteRefs(body), dataIcons(body)...) {
			if !strings.Contains(sprite, `id="i-`+name+`"`) {
				t.Errorf("%s uses icon %q, which is not in the sprite", page, name)
			}
			checked++
		}
	}
	if checked < 10 {
		t.Errorf("only checked %d icon references; the extractor is probably broken", checked)
	}
}

// spriteRefs finds `href="#i-name"` references.
func spriteRefs(body string) []string {
	var names []string
	rest := body
	for {
		index := strings.Index(rest, `href="#i-`)
		if index < 0 {
			return names
		}
		rest = rest[index+len(`href="#i-`):]
		end := strings.IndexByte(rest, '"')
		if end < 0 {
			return names
		}
		names = append(names, rest[:end])
	}
}

// dataIcons finds the `data-icon="name"` placeholders the scripts fill in.
func dataIcons(body string) []string {
	var names []string
	rest := body
	for {
		index := strings.Index(rest, `data-icon="`)
		if index < 0 {
			return names
		}
		rest = rest[index+len(`data-icon="`):]
		end := strings.IndexByte(rest, '"')
		if end < 0 {
			return names
		}
		names = append(names, rest[:end])
	}
}

// -- PWA -------------------------------------------------------------------

func TestEveryPageIsPartOfTheInstallableApp(t *testing.T) {
	// The manifest link is what makes a page installable, and pwa.js is what
	// registers the worker; a page missing either is one where the offline
	// page never gets set up if that is where somebody arrives first.
	site := newRealSite(t)
	for _, target := range append(static.PageRoutes(), "/gift/X", "/no-such-page") {
		_, body := fetch(t, site, target)
		if !strings.Contains(body, `<link rel="manifest" href="/manifest.webmanifest">`) {
			t.Errorf("%s does not link the manifest", target)
		}
		if !strings.Contains(body, `src="/assets/js/pwa.js"`) {
			t.Errorf("%s does not load pwa.js", target)
		}
	}
}

func TestTheManifestDescribesAnInstallableApp(t *testing.T) {
	site := newRealSite(t)
	response, body := fetch(t, site, "/manifest.webmanifest")
	if response.StatusCode != http.StatusOK {
		t.Fatalf("manifest: status %d", response.StatusCode)
	}
	var manifest struct {
		Name     string `json:"name"`
		StartURL string `json:"start_url"`
		Scope    string `json:"scope"`
		Display  string `json:"display"`
		Icons    []struct {
			Src     string `json:"src"`
			Sizes   string `json:"sizes"`
			Purpose string `json:"purpose"`
		} `json:"icons"`
		Shortcuts []struct {
			URL string `json:"url"`
		} `json:"shortcuts"`
	}
	if err := json.Unmarshal([]byte(body), &manifest); err != nil {
		t.Fatalf("manifest is not JSON: %v", err)
	}
	if manifest.Name == "" || manifest.Display != "standalone" {
		t.Errorf("name %q, display %q", manifest.Name, manifest.Display)
	}

	// Chromium's install criteria: a 192 and a 512 icon. A maskable one keeps
	// Android from shrinking the logo onto a white plate.
	sizes := map[string]bool{}
	for _, icon := range manifest.Icons {
		if response, _ := fetch(t, site, icon.Src); response.StatusCode != http.StatusOK {
			t.Errorf("icon %s: status %d", icon.Src, response.StatusCode)
		}
		sizes[icon.Sizes+" "+icon.Purpose] = true
	}
	for _, want := range []string{"192x192 any", "512x512 any", "512x512 maskable"} {
		if !sizes[want] {
			t.Errorf("manifest has no %s icon", want)
		}
	}

	// Every URL the app opens at must be a page the site actually serves.
	routes := map[string]bool{}
	for _, route := range static.PageRoutes() {
		routes[route] = true
	}
	urls := []string{manifest.StartURL}
	for _, shortcut := range manifest.Shortcuts {
		urls = append(urls, shortcut.URL)
	}
	for _, url := range urls {
		if !routes[url] {
			t.Errorf("manifest opens %q, which is not a page", url)
		}
	}
}

func TestTheServiceWorkerPrecachesOnlyWhatExists(t *testing.T) {
	// cache.addAll is all-or-nothing: one 404 in the list and the worker never
	// installs, with nothing on the page to say so.
	site := newRealSite(t)
	_, worker := fetch(t, site, "/sw.js")
	start := strings.Index(worker, "const PRECACHE = [")
	end := strings.Index(worker[start:], "];")
	if start < 0 || end < 0 {
		t.Fatal("PRECACHE list not found in sw.js")
	}
	entries := 0
	for _, line := range strings.Split(worker[start:start+end], "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, `"/`) {
			continue
		}
		target := strings.Trim(strings.TrimSuffix(line, ","), `"`)
		if response, _ := fetch(t, site, target); response.StatusCode != http.StatusOK {
			t.Errorf("sw.js precaches %s, which returns %d", target, response.StatusCode)
		}
		entries++
	}
	if entries < 5 {
		t.Errorf("only found %d precache entries; the parser is probably broken", entries)
	}
	// OFFLINE is named by constant in the list.
	if response, _ := fetch(t, site, "/offline"); response.StatusCode != http.StatusOK {
		t.Errorf("/offline returns %d", response.StatusCode)
	}
}

func TestTheServiceWorkerNeverHandlesTheAPI(t *testing.T) {
	// Answers from /api/ carry subscription links and session state; a cached
	// copy would outlive sign-out. The worker only ever looks at navigations
	// and /assets/.
	site := newRealSite(t)
	_, worker := fetch(t, site, "/sw.js")
	if strings.Contains(worker, `"/api`) {
		t.Error("sw.js mentions /api; it must leave the API to the network")
	}
}
