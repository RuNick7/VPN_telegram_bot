// Command server runs the customer website's backend.
package main

import (
	"context"
	"errors"
	"flag"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/frontend"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/api"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/mailer"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/static"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/yookassa"
)

// routes puts the JSON API and the website on one origin.
//
// One origin rather than two is a security decision, not a convenience: the
// session cookie is `__Host-` prefixed and same-site, there is no CORS policy
// to get wrong, and no preflight surface at all. The API keeps its own
// middleware and its own headers; everything not claimed by it falls through
// to the static site, which sets the document-level ones.
func routes(apiHandler, site http.Handler) http.Handler {
	mux := http.NewServeMux()
	mux.Handle("/api/", apiHandler)
	mux.Handle("/auth/telegram", apiHandler)
	mux.Handle("/", site)
	return mux
}

func main() {
	// Sends one test message and exits. Deliberately a flag on this binary
	// rather than a separate tool: it then reads the same .env, through the
	// same config loader, as the thing whose behaviour it is predicting.
	testMailTo := flag.String("check-smtp", "",
		"send a test message to this address and exit, instead of serving")
	flag.Parse()

	if *testMailTo != "" {
		if err := checkSMTP(*testMailTo); err != nil {
			os.Exit(1)
		}
		return
	}

	log := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(log)

	if err := run(log); err != nil {
		log.Error("fatal", "err", err)
		os.Exit(1)
	}
}

func run(log *slog.Logger) error {
	// Reads the repo-root .env, the same file the bots use, so one file
	// configures the whole deployment. Real environment variables win.
	cfg, err := config.Load(".env", "../.env")
	if err != nil {
		return err
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	st, err := store.Open(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer st.Close()

	ml, err := mailer.New(mailer.Config{
		Host:     cfg.SMTP.Host,
		Port:     cfg.SMTP.Port,
		Username: cfg.SMTP.Username,
		Password: cfg.SMTP.Password,
		From:     cfg.SMTP.From,
		StartTLS: cfg.SMTP.StartTLS,
	})
	if err != nil {
		return err
	}

	panelClient, err := panel.New(
		cfg.Remnawave.BaseURL, cfg.Remnawave.Token,
		cfg.Remnawave.Username, cfg.Remnawave.Password, cfg.Remnawave.Timeout,
	)
	if err != nil {
		return err
	}

	authSvc := auth.NewService(st, ml, cfg.BaseURL, cfg.MagicLinkTTL, cfg.SessionTTL, cfg.TelegramBotToken)
	accountSvc := account.NewService(st, panelClient, cfg.FreeTierEnabled, cfg.WebTrialDays)
	server := api.NewServer(cfg, st, authSvc, accountSvc, yookassa.New(cfg.YooKassaShopID, cfg.YooKassaSecretKey), log)

	site, err := static.New(frontend.Files, static.Options{
		TelegramLogin: cfg.TelegramLoginEnabled(),
		// A year, which is what a preload list wants. Only ever sent on a
		// request that arrived over TLS, so running this on loopback during
		// development cannot pin a browser to HTTPS for localhost.
		HSTSSeconds: 31536000,
	})
	if err != nil {
		return err
	}

	go sweepExpired(ctx, st, log)

	httpServer := &http.Server{
		Addr:    cfg.ListenAddr,
		Handler: routes(server.Routes(), site),
		// A slow or stalled client must not hold a connection open forever.
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      60 * time.Second,
		IdleTimeout:       120 * time.Second,
	}

	errs := make(chan error, 1)
	go func() {
		log.Info("listening", "addr", cfg.ListenAddr, "base_url", cfg.BaseURL,
			"telegram_login", cfg.TelegramLoginEnabled(), "payments", cfg.PaymentsEnabled())
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			errs <- err
		}
	}()

	select {
	case err := <-errs:
		return err
	case <-ctx.Done():
		log.Info("shutting down")
	}

	// Let in-flight requests finish. Cutting them off mid-payment-creation
	// would leave a payment at YooKassa with no pending row here.
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()
	return httpServer.Shutdown(shutdownCtx)
}

// sweepExpired deletes lapsed sessions and spent magic links.
//
// Housekeeping only: nothing depends on it having run, because every read path
// filters on expiry itself. It exists so the tables do not grow without bound.
func sweepExpired(ctx context.Context, st *store.Store, log *slog.Logger) {
	ticker := time.NewTicker(time.Hour)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			sessions, err := st.DeleteExpiredSessions(ctx)
			if err != nil {
				log.Error("sweep sessions", "err", err)
				continue
			}
			links, err := st.DeleteExpiredMagicLinks(ctx)
			if err != nil {
				log.Error("sweep magic links", "err", err)
				continue
			}
			if sessions > 0 || links > 0 {
				log.Info("swept expired auth rows", "sessions", sessions, "magic_links", links)
			}
		}
	}
}
