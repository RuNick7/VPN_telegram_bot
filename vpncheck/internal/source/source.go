// Package source reads what a run checks: a subscription link, a file with a
// subscription in it, or a single share link.
package source

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/RuNick7/vpn-check/internal/redact"
	"github.com/RuNick7/vpn-check/internal/report"
	"github.com/RuNick7/vpn-check/internal/subscription"
)

// Load reads one source and registers its secrets with red. A source that
// could not be read comes back with Error set and no profiles.
func Load(ctx context.Context, source, userAgent string, red *redact.Redactor) (report.Source, []subscription.Profile) {
	source = strings.TrimSpace(source)
	lower := strings.ToLower(source)
	switch {
	case strings.HasPrefix(lower, "http://") || strings.HasPrefix(lower, "https://"):
		red.AddURL(source)
		out := report.Source{URL: source}
		fctx, cancel := context.WithTimeout(ctx, 30*time.Second)
		defer cancel()
		client := &http.Client{Transport: &http.Transport{Proxy: nil}}
		fetched, err := subscription.Fetch(fctx, client, source, userAgent)
		if err != nil {
			out.Error = "не скачивается: " + err.Error()
			return out, nil
		}
		out.Status, out.Took, out.Title, out.UserInfo, out.Notices = fetched.Status, fetched.Took, fetched.Title, fetched.UserInfo, fetched.Notices
		if fetched.Status != http.StatusOK {
			out.Error = fmt.Sprintf("панель ответила HTTP %d", fetched.Status)
			return out, nil
		}
		return parsed(out, fetched.Body, red)
	case strings.Contains(source, "://"):
		red.Add(source)
		out := report.Source{URL: "ссылка " + strings.SplitN(source, "://", 2)[0] + "://"}
		return parsed(out, []byte(source), red)
	default:
		out := report.Source{URL: "файл " + filepath.Base(source)}
		data, err := os.ReadFile(source)
		if err != nil {
			out.Error = "не читается: " + err.Error()
			return out, nil
		}
		return parsed(out, data, red)
	}
}

const noServers = "в подписке нет серверов: подписка закончилась, достигнут лимит устройств или панель не знает это приложение"

// parsed sets Format once the body has been read as a subscription, so an
// Error with no Format means it could not be.
func parsed(out report.Source, body []byte, red *redact.Redactor) (report.Source, []subscription.Profile) {
	profiles, err := subscription.Parse(body)
	if errors.Is(err, subscription.ErrEmpty) {
		out.Format, out.Error = "пустая", noServers
		return out, nil
	}
	if err != nil {
		out.Error = err.Error()
		return out, nil
	}
	for _, profile := range profiles {
		for _, outbound := range profile.Outbounds {
			red.AddConfig(outbound)
		}
	}
	out.Format = "ссылки"
	if trimmed := strings.TrimSpace(string(body)); strings.HasPrefix(trimmed, "[") || strings.HasPrefix(trimmed, "{") {
		out.Format = "Xray JSON"
	}
	out.Profiles = len(profiles)
	out.Servers = len(subscription.Targets(profiles))
	if out.Servers == 0 {
		out.Error = noServers
	}
	return out, profiles
}
