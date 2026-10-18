package main

// What an operator's run adds to a customer's: each node's own log lines
// next to the client's, a summary in the admin chat, and old reports
// cleaned up -- what a daily check from a server or the operator's own
// computer needs.

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/RuNick7/vpn-check/internal/check"
	"github.com/RuNick7/vpn-check/internal/nodelog"
	"github.com/RuNick7/vpn-check/internal/nodes"
	"github.com/RuNick7/vpn-check/internal/report"
)

// operator is what an operator's run knows on top of a customer's.
type operator struct {
	agents []nodes.Agent
	// The admin bot and its chats, for -notify.
	token string
	chats []int64
}

// loadOperator reads the agents and the admin bot from -agents, from the
// bot's own .env given by -env, and from the environment, in that order.
func loadOperator(agentsFlag, envPath string) (*operator, error) {
	values := map[string]string{}
	if envPath != "" {
		var err error
		if values, err = readEnv(envPath); err != nil {
			return nil, err
		}
	}
	get := func(key string) string {
		if value, ok := values[key]; ok {
			return value
		}
		return os.Getenv(key)
	}
	raw := agentsFlag
	if raw == "" {
		raw = get("NODE_LOG_AGENTS")
	}
	agents, errs := nodes.Parse(raw)
	if len(errs) > 0 {
		return nil, errors.Join(errs...)
	}
	op := &operator{agents: agents, token: strings.TrimSpace(get("ADMIN_BOT_TOKEN"))}
	for _, part := range strings.FieldsFunc(get("ADMIN_IDS"), func(r rune) bool { return r == ',' || r == ' ' }) {
		if id, err := strconv.ParseInt(part, 10, 64); err == nil {
			op.chats = append(op.chats, id)
		}
	}
	return op, nil
}

// readEnv reads KEY=VALUE lines the way the bots' .env is written: comments,
// blank lines, an optional "export", values optionally quoted.
func readEnv(path string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	values := map[string]string{}
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(strings.TrimPrefix(line, "export "), "=")
		if !ok {
			continue
		}
		value = strings.TrimSpace(value)
		if len(value) >= 2 && (value[0] == '"' || value[0] == '\'') && value[len(value)-1] == value[0] {
			value = value[1 : len(value)-1]
		} else if i := strings.Index(value, " #"); i >= 0 {
			value = strings.TrimSpace(value[:i])
		}
		values[strings.TrimSpace(key)] = value
	}
	return values, scanner.Err()
}

// nodeQueryBatch keeps each request within what an agent accepts.
const nodeQueryBatch = nodelog.MaxWindows

// askNodes asks every agent for its side of every server in the run.
func askNodes(ctx context.Context, rep *report.Report, agents []nodes.Agent) []report.NodeAnswer {
	slack := 5
	if !rep.Clock.Known {
		slack = 120
	}
	var windows []nodelog.Window
	for _, result := range rep.Results {
		from, to, ok := report.NodeWindow(rep, result)
		if !ok {
			from, to = result.Started.UTC(), result.Started.Add(result.Took).UTC()
		}
		marker := ""
		if result.MarkerSent {
			marker = result.Marker
		}
		windows = append(windows, nodelog.Window{
			Server: result.Target.Endpoint(), From: from, To: to, Marker: marker, Failed: result.Verdict != check.Works,
		})
	}

	answers := make([]report.NodeAnswer, len(agents))
	for i, agent := range agents {
		answers[i].Name = agent.Name
	}
	for start := 0; start < len(windows); start += nodeQueryBatch {
		batch := windows[start:min(start+nodeQueryBatch, len(windows))]
		for i, answer := range nodes.Ask(ctx, agents, nodelog.Query{Windows: batch, SlackSeconds: slack}, 90*time.Second) {
			switch {
			case answers[i].Error != "":
			case answer.Err != nil:
				answers[i].Error = answer.Err.Error()
				answers[i].Sections = nil
			case len(answer.Response.Sections) != len(batch):
				// Sections line up with servers by position, so any other
				// count would put one server's lines under another.
				answers[i].Error = fmt.Sprintf("ответила на %d серверов из %d", len(answer.Response.Sections), len(batch))
				answers[i].Sections = nil
			default:
				answers[i].Files = answer.Response.Files
				answers[i].Sections = append(answers[i].Sections, answer.Response.Sections...)
			}
		}
	}
	return answers
}

// telegramAPI is Telegram's Bot API, replaced in tests.
var telegramAPI = "https://api.telegram.org"

// notify sends the report to every admin chat through the admin bot, with
// the one-line summary as its caption.
func notify(ctx context.Context, op *operator, caption, path string) []error {
	data, err := os.ReadFile(path)
	if err != nil {
		return []error{err}
	}
	if utf8.RuneCountInString(caption) > 1000 {
		caption = string([]rune(caption)[:1000]) + "…"
	}
	client := &http.Client{Timeout: time.Minute}
	var errs []error
	for _, chat := range op.chats {
		if err := sendDocument(ctx, client, op.token, chat, caption, filepath.Base(path), data); err != nil {
			// The token is in the URL: never let it into a message.
			errs = append(errs, fmt.Errorf("чат %d: %s", chat, strings.ReplaceAll(err.Error(), op.token, "***")))
		}
	}
	return errs
}

func sendDocument(ctx context.Context, client *http.Client, token string, chat int64, caption, name string, data []byte) error {
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	_ = form.WriteField("chat_id", strconv.FormatInt(chat, 10))
	_ = form.WriteField("caption", caption)
	part, err := form.CreateFormFile("document", name)
	if err != nil {
		return err
	}
	if _, err := part.Write(data); err != nil {
		return err
	}
	if err := form.Close(); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, telegramAPI+"/bot"+token+"/sendDocument", &body)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", form.FormDataContentType())
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	var answer struct {
		OK          bool   `json:"ok"`
		Description string `json:"description"`
	}
	raw, _ := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	_ = json.Unmarshal(raw, &answer)
	if !answer.OK {
		return fmt.Errorf("Telegram: HTTP %d %s", resp.StatusCode, answer.Description)
	}
	return nil
}

// notifyCaption is the summary line plus what the nodes said.
func notifyCaption(rep *report.Report) string {
	caption := "Проверка серверов: " + report.OneLine(rep)
	if len(rep.Nodes) == 0 {
		return caption
	}
	var failed []string
	for _, node := range rep.Nodes {
		if node.Error != "" {
			failed = append(failed, node.Name)
		}
	}
	if len(failed) > 0 {
		caption += "\nЛоги нод не получены: " + strings.Join(failed, ", ")
	} else {
		caption += "\nЛоги нод получены со всех"
	}
	return caption
}

// prune deletes run directories under root older than days. Only names
// written by report.Write are touched, whatever else the folder holds.
func prune(root string, days int, now time.Time) (int, error) {
	entries, err := os.ReadDir(root)
	if err != nil {
		return 0, err
	}
	removed := 0
	for _, entry := range entries {
		started, err := time.ParseInLocation("2006-01-02_15-04-05", entry.Name(), time.Local)
		if err != nil || !entry.IsDir() || now.Sub(started) < time.Duration(days)*24*time.Hour {
			continue
		}
		if err := os.RemoveAll(filepath.Join(root, entry.Name())); err != nil {
			return removed, err
		}
		removed++
	}
	return removed, nil
}
