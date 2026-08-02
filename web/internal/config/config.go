// Package config loads the website's settings from the same root .env the
// Python bots read, so one file configures the whole deployment.
package config

import (
	"bufio"
	"fmt"
	"os"
	"strconv"
	"strings"
	"time"
)

type Config struct {
	ListenAddr  string
	BaseURL     string // public origin, used to build magic-link URLs
	DatabaseURL string

	SessionTTL   time.Duration
	MagicLinkTTL time.Duration

	SMTP SMTP

	TelegramBotToken    string
	TelegramBotUsername string

	YooKassaShopID    string
	YooKassaSecretKey string

	Remnawave Remnawave

	// Links the frontend renders but does not own. They live in the same .env
	// the bot reads them from, so the offer the site links to and the offer
	// `/docs` links to cannot drift apart.
	Links Links

	// PaidSquadName is the squad a paying -- or trialling -- account belongs
	// in. Same key the bots read, so the two cannot place people differently.
	PaidSquadName     string
	FreeTierEnabled   bool
	LTEEnabled        bool
	LTEFreeGBPerCycle int
	LTECycleDays      int
	TrialDays         int
	// WebTrialDays is the trial granted to someone who signs up on the site
	// and has no panel account yet. Falls back to TRIAL_DAYS so the bot and
	// the site offer the same thing; set to 0 to switch it off.
	WebTrialDays int
}

type SMTP struct {
	Host     string
	Port     int
	Username string
	Password string
	From     string
	// StartTLS upgrades a plaintext connection; false means implicit TLS on
	// connect, which is what port 465 expects.
	StartTLS bool
}

func (s SMTP) Configured() bool { return s.Host != "" && s.From != "" }

type Remnawave struct {
	BaseURL  string
	Token    string
	Username string
	Password string
	Timeout  time.Duration
}

// Links are optional by design. An unset document URL renders as "готовится к
// публикации" rather than as a button to a 404 -- someone looking for the
// refund policy should learn it is not published yet, not be sent to a dead
// page and conclude there isn't one.
type Links struct {
	Offer   string
	Refund  string
	Terms   string
	Privacy string
	Support string
	FAQ     string
}

// Load reads .env files (later files do not override earlier ones, matching
// python-dotenv) and then the process environment, which always wins.
func Load(envFiles ...string) (*Config, error) {
	for _, path := range envFiles {
		if err := loadDotEnv(path); err != nil {
			return nil, fmt.Errorf("read %s: %w", path, err)
		}
	}

	cfg := &Config{
		ListenAddr:   getString("WEB_LISTEN_ADDR", ":8080"),
		BaseURL:      strings.TrimRight(getString("WEB_BASE_URL", ""), "/"),
		DatabaseURL:  getString("DATABASE_URL", ""),
		SessionTTL:   time.Duration(getInt("WEB_SESSION_TTL_HOURS", 720)) * time.Hour,
		MagicLinkTTL: time.Duration(getInt("WEB_MAGIC_LINK_TTL_MINUTES", 15)) * time.Minute,
		SMTP: SMTP{
			Host:     getString("SMTP_HOST", ""),
			Port:     getInt("SMTP_PORT", 587),
			Username: getString("SMTP_USERNAME", ""),
			Password: getString("SMTP_PASSWORD", ""),
			From:     getString("SMTP_FROM", ""),
			StartTLS: getBool("SMTP_STARTTLS", true),
		},
		// The login widget is signed with the bot's own token, so this is the
		// same USER_BOT_TOKEN the customer bot runs on -- not a separate one.
		TelegramBotToken:    getString("USER_BOT_TOKEN", ""),
		TelegramBotUsername: strings.TrimPrefix(getString("TELEGRAM_BOT_USERNAME", ""), "@"),
		YooKassaShopID:      getString("YOOKASSA_SHOP_ID", ""),
		YooKassaSecretKey:   getString("YOOKASSA_SECRET_KEY", ""),
		Remnawave: Remnawave{
			BaseURL:  getString("REMNAWAVE_BASE_URL", ""),
			Token:    firstNonEmpty(getString("REMNAWAVE_TOKEN", ""), getString("REMNAWAVE_API_KEY", "")),
			Username: getString("REMNAWAVE_USERNAME", ""),
			Password: getString("REMNAWAVE_PASSWORD", ""),
			Timeout:  time.Duration(getInt("REMNAWAVE_TIMEOUT_SECONDS", 10)) * time.Second,
		},
		Links: Links{
			Offer:   getString("OFFER_URL", ""),
			Refund:  getString("REFUND_POLICY_URL", ""),
			Terms:   getString("TERMS_URL", ""),
			Privacy: getString("PRIVACY_POLICY_URL", ""),
			Support: getString("SUPPORT_URL", ""),
			FAQ:     getString("FAQ_URL", ""),
		},
		PaidSquadName:     getString("PAID_SQUAD_NAME", "internal"),
		FreeTierEnabled:   getBool("FREE_TIER_ENABLED", false),
		LTEEnabled:        getBool("LTE_ENABLED", false),
		LTEFreeGBPerCycle: getInt("LTE_FREE_GB_PER_CYCLE", 10),
		LTECycleDays:      getInt("LTE_CYCLE_DAYS", 30),
		TrialDays:         getInt("TRIAL_DAYS", 30),
	}
	cfg.WebTrialDays = getInt("WEB_TRIAL_DAYS", cfg.TrialDays)
	if cfg.WebTrialDays < 0 {
		cfg.WebTrialDays = 0
	}
	return cfg, cfg.Validate()
}

// Validate fails closed on anything whose absence would make the site behave
// insecurely rather than merely badly.
//
// There is deliberately no session-signing secret to get wrong. Sessions are
// opaque random tokens stored hashed in Postgres, so the class of bug this
// project shipped before -- a JWT secret defaulting to "change_me" and no
// startup check -- cannot exist here: there is nothing to sign and nothing to
// forge without the database.
func (c *Config) Validate() error {
	var problems []string

	if c.DatabaseURL == "" {
		problems = append(problems, "DATABASE_URL is required")
	}
	if c.BaseURL == "" {
		problems = append(problems, "WEB_BASE_URL is required (magic links are built from it)")
	}
	// A magic link is only as private as the channel it travels on. Without a
	// real sender the previous implementation put the token in the API
	// response, which meant "email verification" verified nothing at all --
	// anyone could claim any address. Refusing to start is the honest
	// alternative to silently shipping that again.
	if !c.SMTP.Configured() {
		problems = append(problems, "SMTP_HOST and SMTP_FROM are required to send login links")
	}
	if c.Remnawave.BaseURL == "" {
		problems = append(problems, "REMNAWAVE_BASE_URL is required")
	}
	if c.Remnawave.Token == "" && (c.Remnawave.Username == "" || c.Remnawave.Password == "") {
		problems = append(problems,
			"Remnawave needs REMNAWAVE_TOKEN/REMNAWAVE_API_KEY or REMNAWAVE_USERNAME + REMNAWAVE_PASSWORD")
	}

	if len(problems) == 0 {
		return nil
	}
	return fmt.Errorf("configuration is incomplete:\n  - %s", strings.Join(problems, "\n  - "))
}

// TelegramLoginEnabled reports whether the Telegram login widget can be used.
// Unlike the checks above this is optional: email is a complete login route on
// its own, so a missing bot token disables one button rather than the site.
func (c *Config) TelegramLoginEnabled() bool { return c.TelegramBotToken != "" }

// PaymentsEnabled reports whether new payments can be created.
func (c *Config) PaymentsEnabled() bool {
	return c.YooKassaShopID != "" && c.YooKassaSecretKey != ""
}

// -- env helpers ------------------------------------------------------------

func loadDotEnv(path string) error {
	file, err := os.Open(path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil // running from real environment variables is fine
		}
		return err
	}
	defer file.Close()

	scanner := bufio.NewScanner(file)
	for scanner.Scan() {
		key, value, ok := parseDotEnvLine(scanner.Text())
		if !ok {
			continue
		}
		// Never overwrite: the real environment is authoritative, which is
		// what lets compose inject secrets over a checked-in .env.
		if _, exists := os.LookupEnv(key); !exists {
			os.Setenv(key, value)
		}
	}
	return scanner.Err()
}

func parseDotEnvLine(line string) (key, value string, ok bool) {
	line = strings.TrimSpace(line)
	if line == "" || strings.HasPrefix(line, "#") {
		return "", "", false
	}
	key, value, found := strings.Cut(line, "=")
	if !found {
		return "", "", false
	}
	key = strings.TrimSpace(strings.TrimPrefix(key, "export "))
	value = strings.TrimSpace(value)
	if len(value) >= 2 {
		if (value[0] == '"' && value[len(value)-1] == '"') ||
			(value[0] == '\'' && value[len(value)-1] == '\'') {
			value = value[1 : len(value)-1]
		}
	}
	return key, value, key != ""
}

func getString(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func getInt(key string, fallback int) int {
	if v, err := strconv.Atoi(getString(key, "")); err == nil {
		return v
	}
	return fallback
}

func getBool(key string, fallback bool) bool {
	switch strings.ToLower(getString(key, "")) {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	}
	return fallback
}

func firstNonEmpty(values ...string) string {
	for _, v := range values {
		if v != "" {
			return v
		}
	}
	return ""
}
