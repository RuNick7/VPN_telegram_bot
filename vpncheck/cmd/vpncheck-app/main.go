// vpncheck-app is vpncheck for customers: one field for the subscription
// link and a few buttons, in a window of its own on macOS and Windows, in
// the Android app's on a phone, and in the browser elsewhere. The page and
// everything behind it are internal/app; this only starts it on this device
// alone.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/RuNick7/vpn-check/internal/app"
	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/phone"
	"github.com/RuNick7/vpn-check/internal/subscription"
)

// Set at build time (build.sh).
var (
	version = "dev"
	// The hosts subscription links are on, comma-separated.
	domains = ""
	// The website: subscription status, and where «Отправить в поддержку»
	// sends the report.
	site = ""
)

// With the page closed and no check running, the app has nothing left to do.
const idleExit = 3 * time.Minute

const appTitle = "KairaVPN Проверка"

func main() {
	// Before anything resolves a name, in a tunnel worker too: see phone.
	if path := os.Getenv(phone.FileEnv); path != "" {
		phone.Use(path)
	}
	check.ServeWorker()
	os.Exit(run())
}

func run() int {
	noBrowser := flag.Bool("no-browser", false, "не открывать браузер, только напечатать адрес")
	inBrowser := flag.Bool("browser", false, "открыть проверку в браузере, а не в своём окне")
	showVersion := flag.Bool("version", false, "показать версию")
	flag.Parse()
	if *showVersion {
		fmt.Printf("vpncheck-app %s (Xray %s, %s/%s)\n", version, check.XrayVersion(), runtime.GOOS, runtime.GOARCH)
		return 0
	}

	opts := check.DefaultOptions()
	// A short download through each server: enough to catch a connection
	// that stalls after the first few kilobytes, quick enough for every one.
	opts.SpeedBytes = 1 << 20
	cfg := app.Config{
		Version:   version,
		Domains:   splitList(domains),
		Dir:       dataDir("reports"),
		Downloads: app.DownloadsDir(),
		LinkFile:  configFile("subscription"),
		UserAgent: subscription.DefaultUserAgent,
		Options:   opts,
		Site:      site,
	}

	// Started by the Android app, which shows the page itself.
	if path := os.Getenv(phone.FileEnv); path != "" {
		// "Android 14, Xiaomi 23053RN02Y": the report's device line.
		if system := os.Getenv("VPNCHECK_SYSTEM"); system != "" {
			cfg.Platform = system + ", " + runtime.GOARCH
		}
		cfg.Metered = func() bool { return phone.Read(path).Metered }
		return runPhone(cfg)
	}

	if hasWindow && !*inBrowser && !*noBrowser && webviewInstalled() {
		cfg.Window = true
		a := app.New(cfg, "")
		smoke := newSmokeTest()
		err := runWindow(a, smoke)
		if err == nil {
			// A check the window was closed on stops with it.
			a.Stop()
			for deadline := time.Now().Add(5 * time.Second); a.Busy() && time.Now().Before(deadline); {
				time.Sleep(100 * time.Millisecond)
			}
			if smoke != nil && smoke.failed {
				return 1
			}
			return 0
		}
		// The window could not open: the same page in the browser, then.
		fmt.Fprintln(os.Stderr, "Окно не открылось, открываю проверку в браузере:", err)
		cfg.Window = false
	}
	return runBrowser(cfg, *noBrowser)
}

// serve serves the page on 127.0.0.1 and returns its address, key
// included. Port 0: a free one, so two copies never fight over it. Loopback
// only: nothing outside this device can reach the page, and what on it can
// gets nowhere without the key.
func serve(cfg app.Config) (*app.App, *http.Server, string, error) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return nil, nil, "", err
	}
	var raw [16]byte
	_, _ = rand.Read(raw[:])
	token := hex.EncodeToString(raw[:])
	a := app.New(cfg, token)

	server := &http.Server{Handler: a.Handler(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
			fmt.Fprintln(os.Stderr, err)
		}
	}()
	return a, server, fmt.Sprintf("http://%s/#k=%s", listener.Addr(), token), nil
}

// runBrowser serves the page and opens it in the browser, and exits once
// the page has been closed for a while.
func runBrowser(cfg app.Config, noBrowser bool) int {
	a, server, url, err := serve(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Не удалось запустить проверку:", err)
		return 2
	}
	fmt.Printf("vpncheck %s — проверка серверов VPN\n\n", version)
	fmt.Println("Проверка открыта в браузере. Не закрывайте это окно, пока она идёт.")
	if noBrowser {
		fmt.Println("Адрес:", url)
	} else if err := app.OpenBrowser(url); err != nil {
		fmt.Println("Браузер не открылся. Откройте этот адрес сами:", url)
	} else {
		fmt.Println("Если браузер не открылся, откройте адрес:", url)
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	tick := time.NewTicker(10 * time.Second)
	defer tick.Stop()
	for {
		select {
		case <-ctx.Done():
		case <-tick.C:
			if a.Busy() || a.Idle() < idleExit {
				continue
			}
			fmt.Println("Страница проверки закрыта, выхожу.")
		}
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		_ = server.Shutdown(shutdown)
		cancel()
		return 0
	}
}

// runPhone serves the page for the Android app, which reads the address
// from the first line it prints and shows the page in its own window. It
// runs until the app stops it, or until the app is gone: the end of stdin,
// which is a pipe from the app, says so even when the app was killed and
// could not stop it.
func runPhone(cfg app.Config) int {
	a, server, url, err := serve(cfg)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Не удалось запустить проверку:", err)
		return 2
	}
	fmt.Println("URL " + url)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	gone := make(chan struct{})
	go func() {
		_, _ = io.Copy(io.Discard, os.Stdin)
		close(gone)
	}()
	select {
	case <-ctx.Done():
	case <-gone:
	}
	a.Stop()
	shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	_ = server.Shutdown(shutdown)
	cancel()
	return 0
}

func splitList(value string) []string {
	var out []string
	for _, item := range strings.Split(value, ",") {
		if item = strings.TrimSpace(item); item != "" {
			out = append(out, item)
		}
	}
	return out
}

// dataDir is where runs go: the user's cache directory, which the system
// may clear, and that is fine -- a saved report is copied to Downloads.
func dataDir(name string) string {
	base, err := os.UserCacheDir()
	if err != nil {
		base = os.TempDir()
	}
	return filepath.Join(base, "vpncheck", name)
}

func configFile(name string) string {
	base, err := os.UserConfigDir()
	if err != nil {
		return ""
	}
	return filepath.Join(base, "vpncheck", name)
}
