package nodelog

import (
	"errors"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"
)

const (
	accessLog = `2026/10/16 19:59:30.000000 from 198.51.100.7:49999 accepted tcp:example.org:443 [vless-in >> direct] email: u-cust
2026/10/16 20:00:00.100000 from 203.0.113.9:40000 accepted tcp:www.google.com:443 [vless-in >> direct] email: u-other
2026/10/16 20:00:01.000000 from 198.51.100.7:50001 accepted tcp:cp.cloudflare.com:80 [vless-in >> direct] email: u-cust
2026/10/16 20:00:03.000000 from 198.51.100.7:50002 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80 [vless-in >> direct] email: u-cust
2026/10/16 20:00:03.500000 from 203.0.113.9:40001 accepted tcp:cp.cloudflare.com:80 [vless-in >> direct] email: u-other
2026/10/16 20:10:00.000000 from 198.51.100.7:50003 accepted tcp:example.com:443 [vless-in >> direct] email: u-cust
`
	errorLog = `2026/10/16 20:00:02.000000 [Info] [1234] proxy/vless/inbound: received request from 198.51.100.7:50001
2026/10/16 20:00:02.500000 [Warning] [999] app/dispatcher: default route for 203.0.113.9:40000
2026/10/16 20:00:02.600000 [Warning] [998] app/dispatcher: default route for 198.51.100.70:1
2026/10/16 20:00:20.000000 [Info] REALITY: processed invalid connection from 192.0.2.44:6000
2026/10/16 20:00:20.500000 from 192.0.2.50:7000 accepted tcp:example.net:443 [vless-in >> direct] email: u-third
`
)

func logs(t *testing.T) []string {
	t.Helper()
	dir := t.TempDir()
	access, errorPath := filepath.Join(dir, "access.log"), filepath.Join(dir, "error.log")
	// The first line has rotated away already.
	lines := strings.SplitAfterN(accessLog, "\n", 2)
	write(t, access+".1", lines[0])
	write(t, access, lines[1])
	write(t, errorPath, errorLog)
	return []string{access, errorPath, filepath.Join(dir, "missing.log")}
}

func write(t *testing.T, path, text string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
}

func at(clock string) time.Time {
	parsed, err := time.Parse(time.RFC3339, "2026-10-16T"+clock+"Z")
	if err != nil {
		panic(err)
	}
	return parsed
}

func TestMarkerFindsTheUserAndTheirAddress(t *testing.T) {
	sections, files, err := Search(logs(t), time.UTC, Query{
		Windows:      []Window{{Server: "de1:443", From: at("20:00:00"), To: at("20:00:04"), Marker: "vpncheck-0a1b2c3d-01.invalid"}},
		SlackSeconds: 1,
	})
	if err != nil {
		t.Fatal(err)
	}
	if len(files) != 4 || files[3].Error == "" || files[0].Error != "" {
		t.Fatalf("files %+v", files)
	}
	s := sections[0]
	if !s.Attributed || !slices.Equal(s.Emails, []string{"u-cust"}) || !slices.Equal(s.Addresses, []string{"198.51.100.7"}) {
		t.Fatalf("%+v", s)
	}
	want := []string{
		"2026/10/16 20:00:01.000000 from 198.51.100.7:50001 accepted tcp:cp.cloudflare.com:80",
		"2026/10/16 20:00:02.000000 [Info] [1234] proxy/vless/inbound: received request from 198.51.100.7:50001",
		"2026/10/16 20:00:03.000000 from 198.51.100.7:50002 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80",
	}
	if len(s.Lines) != len(want) {
		t.Fatalf("lines:\n%s", strings.Join(s.Lines, "\n"))
	}
	for i, prefix := range want {
		if !strings.HasPrefix(s.Lines[i], prefix) {
			t.Errorf("line %d: %s", i, s.Lines[i])
		}
	}
}

func TestWindowsAreSearchedOnTheirOwn(t *testing.T) {
	sections, _, err := Search(logs(t), time.UTC, Query{
		Windows: []Window{
			// A server that refused the client: no marker, nothing to
			// attribute, so the node's own complaints at the time.
			{Server: "nl1:443", From: at("20:00:19"), To: at("20:00:21"), Marker: "vpncheck-0a1b2c3d-02.invalid", Failed: true},
			// The same, for a server that worked: nothing worth sending.
			{Server: "fi1:443", From: at("20:00:19"), To: at("20:00:21"), Marker: "vpncheck-0a1b2c3d-03.invalid"},
			// No marker, but the panel name the bot knows.
			{Server: "de2:443", From: at("20:09:59"), To: at("20:10:01"), Marker: "vpncheck-0a1b2c3d-04.invalid"},
			// The window before the log rotated.
			{Server: "de3:443", From: at("19:59:29"), To: at("19:59:31"), Marker: "x.invalid"},
		},
		Users: []string{"u-cust"},
	})
	if err != nil {
		t.Fatal(err)
	}
	failed := sections[0]
	if failed.Attributed || len(failed.Lines) != 1 || !strings.Contains(failed.Lines[0], "REALITY") {
		t.Errorf("failed window: %+v", failed)
	}
	if worked := sections[1]; len(worked.Lines) != 0 {
		t.Errorf("working window: %+v", worked)
	}
	byUser := sections[2]
	if !slices.Equal(byUser.Emails, []string{"u-cust"}) || len(byUser.Lines) != 1 || !strings.Contains(byUser.Lines[0], "example.com") {
		t.Errorf("by user: %+v", byUser)
	}
	if rotated := sections[3]; len(rotated.Lines) != 1 || !strings.Contains(rotated.Lines[0], "example.org") {
		t.Errorf("rotated: %+v", rotated)
	}
}

func TestNodeTimeZone(t *testing.T) {
	moscow := time.FixedZone("MSK", 3*3600)
	dir := t.TempDir()
	path := filepath.Join(dir, "access.log")
	write(t, path, "2026/10/16 23:00:03.000000 from 198.51.100.7:50002 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80 [in >> out] email: u-cust\n")
	sections, _, err := Search([]string{path}, moscow, Query{
		Windows: []Window{{From: at("20:00:00"), To: at("20:00:04"), Marker: "vpncheck-0a1b2c3d-01.invalid"}},
	})
	if err != nil || len(sections[0].Lines) != 1 {
		t.Fatalf("%+v %v", sections, err)
	}
}

func TestBadQueries(t *testing.T) {
	ok := Window{From: at("20:00:00"), To: at("20:00:04")}
	for name, q := range map[string]Query{
		"no windows":     {},
		"backwards":      {Windows: []Window{{From: at("20:00:04"), To: at("20:00:00")}}},
		"too long":       {Windows: []Window{{From: at("10:00:00"), To: at("20:00:00")}}},
		"too much slack": {Windows: []Window{ok}, SlackSeconds: 3600},
		"too many":       {Windows: slices.Repeat([]Window{ok}, MaxWindows+1)},
	} {
		if _, _, err := Search(nil, time.UTC, q); !errors.Is(err, ErrQuery) {
			t.Errorf("%s: %v", name, err)
		}
	}
}

func TestParseAccess(t *testing.T) {
	for line, want := range map[string]access{
		"2026/10/16 20:17:16.225156 from 127.0.0.1:46320 accepted tcp:vpncheck-0a1b2c3d-01.invalid:80 email: u-test":              {"127.0.0.1", "u-test"},
		"2026/10/16 20:17:16 from tcp:[2001:db8::1]:443 accepted udp:1.1.1.1:53 [hy-in >> direct] email: 42":                      {"2001:db8::1", "42"},
		"2026/10/16 20:17:16.225156 from 198.51.100.7:1 rejected tcp:ads.example:443 [in -> block] blocked by rule email: u-test": {"198.51.100.7", "u-test"},
	} {
		got, ok := parseAccess(line)
		if !ok || got != want {
			t.Errorf("%s: %+v %v", line, got, ok)
		}
	}
	if _, ok := parseAccess("2026/10/16 20:00:02 [Info] received request from 1.2.3.4:5 to x"); ok {
		t.Error("error line read as access")
	}
}

func TestMentionsAny(t *testing.T) {
	if !mentionsAny("conn from 1.2.3.4:5 closed", []string{"1.2.3.4"}) || !mentionsAny("1.2.3.4", []string{"1.2.3.4"}) {
		t.Error("missed")
	}
	if mentionsAny("from 11.2.3.45:5", []string{"1.2.3.4"}) || mentionsAny("from 1.2.3.40:5", []string{"1.2.3.4"}) {
		t.Error("matched part of another address")
	}
}
