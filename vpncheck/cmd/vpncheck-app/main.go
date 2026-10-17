// vpncheck-app is vpncheck for customers: one field for the subscription
// link and a few buttons, in the browser for now. The page and everything
// behind it are internal/app; this only starts it on this computer alone.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/app"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/check"
	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/subscription"
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

func main() {
	check.ServeWorker()
	os.Exit(run())
}

func run() int {
	noBrowser := flag.Bool("no-browser", false, "не открывать браузер, только напечатать адрес")
	showVersion := flag.Bool("version", false, "показать версию")
	flag.Parse()
	if *showVersion {
		fmt.Printf("vpncheck-app %s (Xray %s, %s/%s)\n", version, check.XrayVersion(), runtime.GOOS, runtime.GOARCH)
		return 0
	}

	// Port 0: a free one, so two copies never fight over it. Loopback only:
	// nothing outside this computer can reach the page.
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fmt.Fprintln(os.Stderr, "Не удалось запустить проверку:", err)
		return 2
	}
	var raw [16]byte
	_, _ = rand.Read(raw[:])
	token := hex.EncodeToString(raw[:])

	opts := check.DefaultOptions()
	// A short download through each server: enough to catch a connection
	// that stalls after the first few kilobytes, quick enough for every one.
	opts.SpeedBytes = 1 << 20
	a := app.New(app.Config{
		Version:   version,
		Domains:   splitList(domains),
		Dir:       dataDir("reports"),
		Downloads: app.DownloadsDir(),
		LinkFile:  configFile("subscription"),
		UserAgent: subscription.DefaultUserAgent,
		Options:   opts,
		Site:      site,
	}, token)

	server := &http.Server{Handler: a.Handler(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		if err := server.Serve(listener); err != nil && !errors.Is(err, http.ErrServerClosed) {
			fmt.Fprintln(os.Stderr, err)
		}
	}()

	url := fmt.Sprintf("http://%s/#k=%s", listener.Addr(), token)
	fmt.Printf("vpncheck %s — проверка серверов VPN\n\n", version)
	fmt.Println("Проверка открыта в браузере. Не закрывайте это окно, пока она идёт.")
	if *noBrowser {
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
