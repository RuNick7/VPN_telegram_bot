// Package nodelog finds one vpncheck run in a node's Xray logs.
//
// A run asks every server it checks for a host named after it (see
// check.Marker). The node's access log records that request like any other:
// the time, the address it came from, and the user it authenticated as. From
// that one line the rest follows -- every line of that user, and every line
// naming that address, while the check ran.
//
// A server that refused the client never learns who it was, so its log has
// no marker and no user. For such a window only the time is left, and the
// node's error lines from that time are returned as they are, marked as not
// attributed to anyone.
package nodelog

import (
	"bufio"
	"errors"
	"io"
	"net"
	"os"
	"slices"
	"strings"
	"time"
)

// Window is one server's part of a run: when its node saw the run, in real
// time, and the marker host it was sent.
type Window struct {
	Server string    `json:"server"`
	From   time.Time `json:"from"`
	To     time.Time `json:"to"`
	Marker string    `json:"marker"`
	// The check failed, so lines that cannot be attributed are worth seeing.
	Failed bool `json:"failed"`
}

type Query struct {
	Windows []Window `json:"windows"`
	// Names the user may have in the panel, used when no marker turns up.
	Users []string `json:"users"`
	// How far around each window to look: the customer's clock, even
	// corrected, and the node's are not the same clock.
	SlackSeconds int `json:"slack_seconds"`
}

// Section is what one node's logs hold for one window.
type Section struct {
	Window
	Emails    []string `json:"emails"`
	Addresses []string `json:"addresses"`
	// Found by the marker or a user name. False means the lines are only
	// what the node logged at that time, whoever it was about.
	Attributed bool     `json:"attributed"`
	Lines      []string `json:"lines"`
	Truncated  bool     `json:"truncated"`
}

// Response is what an agent answers: its name, the logs it read, and one
// section per window of the query, in the same order.
type Response struct {
	Node     string    `json:"node"`
	Files    []File    `json:"files"`
	Sections []Section `json:"sections,omitempty"`
}

// File says whether a log could be read.
type File struct {
	Path  string `json:"path"`
	Size  int64  `json:"size"`
	Error string `json:"error,omitempty"`
}

const (
	MaxWindows      = 100
	MaxWindowLength = time.Hour
	MaxSlack        = 10 * time.Minute
	// Per window: enough for a minute of one user's traffic, and a bound on
	// what a busy node's unattributed lines can add.
	MaxLines           = 3000
	maxUnattributed    = 300
	maxCollected       = 500_000
	scannerBufferBytes = 1 << 20
)

var ErrQuery = errors.New("bad query")

func (q Query) validate() error {
	if len(q.Windows) == 0 || len(q.Windows) > MaxWindows {
		return ErrQuery
	}
	if q.SlackSeconds < 0 || time.Duration(q.SlackSeconds)*time.Second > MaxSlack {
		return ErrQuery
	}
	for _, w := range q.Windows {
		if w.From.IsZero() || w.To.Before(w.From) || w.To.Sub(w.From) > MaxWindowLength {
			return ErrQuery
		}
	}
	return nil
}

type entry struct {
	at   time.Time
	text string
}

// Search reads the logs once and answers every window of the query. A path
// that cannot be read is reported in the files and skipped; the rotated
// copy next to each log (path.1) is read too, for a window that spans the
// rotation.
func Search(paths []string, loc *time.Location, q Query) ([]Section, []File, error) {
	if err := q.validate(); err != nil {
		return nil, nil, err
	}
	slack := time.Duration(q.SlackSeconds) * time.Second
	from, to := q.Windows[0].From, q.Windows[0].To
	for _, w := range q.Windows {
		from, to = minTime(from, w.From), maxTime(to, w.To)
	}
	from, to = from.Add(-slack), to.Add(slack)

	var entries []entry
	var files []File
	for _, path := range paths {
		for _, candidate := range []string{path + ".1", path} {
			file := File{Path: candidate}
			info, err := os.Stat(candidate)
			if err != nil {
				if candidate == path {
					file.Error = err.Error()
					files = append(files, file)
				}
				continue
			}
			file.Size = info.Size()
			found, err := read(candidate, loc, from, to, maxCollected-len(entries))
			if err != nil {
				file.Error = err.Error()
			}
			entries = append(entries, found...)
			files = append(files, file)
		}
	}
	slices.SortStableFunc(entries, func(a, b entry) int { return a.at.Compare(b.at) })

	sections := make([]Section, len(q.Windows))
	for i, w := range q.Windows {
		sections[i] = match(w, slack, q.Users, entries)
	}
	return sections, files, nil
}

func read(path string, loc *time.Location, from, to time.Time, room int) ([]entry, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	return scan(f, loc, from, to, room)
}

func scan(r io.Reader, loc *time.Location, from, to time.Time, room int) ([]entry, error) {
	var found []entry
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 64<<10), scannerBufferBytes)
	for scanner.Scan() {
		line := scanner.Text()
		at, ok := lineTime(line, loc)
		if !ok || at.Before(from) || at.After(to) {
			continue
		}
		if len(found) >= room {
			break
		}
		found = append(found, entry{at: at, text: line})
	}
	return found, scanner.Err()
}

// lineTime reads the timestamp Xray starts each line with, in the node's
// time zone: 2006/01/02 15:04:05, with microseconds when Xray writes them.
func lineTime(line string, loc *time.Location) (time.Time, bool) {
	for _, layout := range []string{"2006/01/02 15:04:05.000000", "2006/01/02 15:04:05"} {
		if len(line) >= len(layout) {
			if at, err := time.ParseInLocation(layout, line[:len(layout)], loc); err == nil {
				return at, true
			}
		}
	}
	return time.Time{}, false
}

// access is one line of Xray's access log:
//
//	2026/10/16 20:17:16.225156 from 1.2.3.4:46320 accepted tcp:example.com:80 [in >> out] email: u-1
type access struct {
	address string
	email   string
}

func parseAccess(line string) (access, bool) {
	_, rest, ok := strings.Cut(line, " from ")
	if !ok {
		return access{}, false
	}
	source, rest, ok := strings.Cut(rest, " ")
	if !ok || !(strings.HasPrefix(rest, "accepted ") || strings.HasPrefix(rest, "rejected ")) {
		return access{}, false
	}
	var a access
	source = strings.TrimPrefix(strings.TrimPrefix(source, "tcp:"), "udp:")
	if host, _, err := net.SplitHostPort(source); err == nil {
		a.address = host
	} else {
		a.address = source
	}
	if i := strings.LastIndex(rest, " email: "); i >= 0 {
		a.email = strings.TrimSpace(rest[i+len(" email: "):])
	}
	return a, true
}

func match(w Window, slack time.Duration, users []string, entries []entry) Section {
	section := Section{Window: w}
	from, to := w.From.Add(-slack), w.To.Add(slack)
	start, _ := slices.BinarySearchFunc(entries, from, func(e entry, t time.Time) int { return e.at.Compare(t) })
	var inWindow []entry
	for _, e := range entries[start:] {
		if e.at.After(to) {
			break
		}
		inWindow = append(inWindow, e)
	}

	emails := map[string]bool{}
	addresses := map[string]bool{}
	if w.Marker != "" {
		for _, e := range inWindow {
			if strings.Contains(e.text, w.Marker) {
				if a, ok := parseAccess(e.text); ok {
					if a.email != "" {
						emails[a.email] = true
					}
					if a.address != "" {
						addresses[a.address] = true
					}
				}
			}
		}
	}
	if len(emails) == 0 && len(users) > 0 {
		for _, e := range inWindow {
			if a, ok := parseAccess(e.text); ok && a.email != "" && slices.Contains(users, a.email) {
				emails[a.email] = true
			}
		}
	}
	// Every address the user came from while the window was open: the
	// error log names a connection by its address, never by its user.
	for _, e := range inWindow {
		if a, ok := parseAccess(e.text); ok && emails[a.email] && a.address != "" {
			addresses[a.address] = true
		}
	}

	section.Emails = sortedKeys(emails)
	section.Addresses = sortedKeys(addresses)
	section.Attributed = len(emails) > 0 || len(addresses) > 0
	limit := MaxLines
	for _, e := range inWindow {
		keep := false
		if section.Attributed {
			if a, ok := parseAccess(e.text); ok {
				// By user when there is one: an address can be shared -- a
				// carrier's NAT puts strangers behind it.
				if len(emails) > 0 {
					keep = emails[a.email]
				} else {
					keep = addresses[a.address]
				}
			} else {
				keep = mentionsAny(e.text, section.Addresses)
			}
		} else if w.Failed {
			// Nothing names the run. What the node complained about at the
			// time is still the best evidence there is -- but only its own
			// complaints, not everyone's traffic.
			_, isAccess := parseAccess(e.text)
			keep = !isAccess
			limit = maxUnattributed
		}
		if !keep {
			continue
		}
		if len(section.Lines) >= limit {
			section.Truncated = true
			break
		}
		section.Lines = append(section.Lines, e.text)
	}
	return section
}

// mentionsAny reports whether line names one of the addresses as a whole
// address: 1.2.3.4 is not in 11.2.3.45.
func mentionsAny(line string, addresses []string) bool {
	for _, address := range addresses {
		for offset := 0; ; {
			i := strings.Index(line[offset:], address)
			if i < 0 {
				break
			}
			i += offset
			end := i + len(address)
			if (i == 0 || !addressChar(line[i-1])) && (end == len(line) || !addressChar(line[end])) {
				return true
			}
			offset = i + 1
		}
	}
	return false
}

func addressChar(c byte) bool {
	return c == '.' || (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F')
}

func sortedKeys(set map[string]bool) []string {
	keys := make([]string, 0, len(set))
	for key := range set {
		keys = append(keys, key)
	}
	slices.Sort(keys)
	return keys
}

func minTime(a, b time.Time) time.Time {
	if b.Before(a) {
		return b
	}
	return a
}

func maxTime(a, b time.Time) time.Time {
	if b.After(a) {
		return b
	}
	return a
}
