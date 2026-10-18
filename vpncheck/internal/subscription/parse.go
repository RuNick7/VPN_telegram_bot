package subscription

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"strings"
)

// Profile is one entry of a subscription as an app lists it: a name and the
// outbounds behind it.
type Profile struct {
	Name      string
	Outbounds []map[string]any
}

// ErrUnknownFormat means the body is neither Xray JSON nor a list of links.
var ErrUnknownFormat = errors.New("неизвестный формат подписки")

// ErrEmpty means the panel answered with nothing at all, which is how it
// turns away a subscription it will not serve.
var ErrEmpty = errors.New("подписка пустая")

// Parse reads whichever of the two formats the panel answered with: Xray
// JSON configs (what Happ gets) or share links, plain or base64-encoded
// (what everything else gets).
func Parse(body []byte) ([]Profile, error) {
	trimmed := bytes.TrimSpace(bytes.TrimPrefix(body, []byte("\xef\xbb\xbf")))
	if len(trimmed) == 0 {
		return nil, ErrEmpty
	}
	if trimmed[0] == '[' || trimmed[0] == '{' {
		return parseJSON(trimmed)
	}
	text := string(trimmed)
	if !strings.Contains(text, "://") {
		decoded, ok := decodeBase64(text)
		if !ok {
			return nil, ErrUnknownFormat
		}
		text = decoded
	}
	return parseLinks(text)
}

func parseJSON(body []byte) ([]Profile, error) {
	var configs []map[string]any
	if body[0] == '{' {
		var single map[string]any
		if err := json.Unmarshal(body, &single); err != nil {
			return nil, fmt.Errorf("подписка в JSON не читается: %w", err)
		}
		configs = []map[string]any{single}
	} else if err := json.Unmarshal(body, &configs); err != nil {
		return nil, fmt.Errorf("подписка в JSON не читается: %w", err)
	}

	var profiles []Profile
	for index, config := range configs {
		raw, _ := config["outbounds"].([]any)
		if len(raw) == 0 {
			continue
		}
		outbounds := make([]map[string]any, 0, len(raw))
		for _, item := range raw {
			if outbound, ok := item.(map[string]any); ok {
				outbounds = append(outbounds, outbound)
			}
		}
		// sing-box keeps its outbounds in the same key, under "type" rather
		// than "protocol". Checking one with Xray would report every server
		// broken for a reason that has nothing to do with the servers.
		if len(outbounds) > 0 && str(outbounds[0], "protocol") == "" && str(outbounds[0], "type") != "" {
			return nil, errors.New("панель отдала подписку для sing-box; запустите с -ua " + DefaultUserAgent)
		}
		name := str(config, "remarks")
		if name == "" {
			name = fmt.Sprintf("Профиль %d", index+1)
		}
		profiles = append(profiles, Profile{Name: name, Outbounds: outbounds})
	}
	return profiles, nil
}

func parseLinks(text string) ([]Profile, error) {
	var profiles []Profile
	var problems []string
	for _, line := range strings.Split(text, "\n") {
		line = strings.TrimSpace(line)
		if line == "" || !strings.Contains(line, "://") {
			continue
		}
		outbound, name, err := LinkToOutbound(line)
		if err != nil {
			problems = append(problems, err.Error())
			continue
		}
		profiles = append(profiles, Profile{Name: name, Outbounds: []map[string]any{outbound}})
	}
	if len(profiles) == 0 && len(problems) > 0 {
		return nil, fmt.Errorf("ни одна ссылка не разобрана: %s", strings.Join(problems, "; "))
	}
	return profiles, nil
}

func decodeBase64(text string) (string, bool) {
	compact := strings.Join(strings.Fields(text), "")
	for _, encoding := range []*base64.Encoding{
		base64.StdEncoding, base64.RawStdEncoding, base64.URLEncoding, base64.RawURLEncoding,
	} {
		if decoded, err := encoding.DecodeString(compact); err == nil {
			return string(decoded), true
		}
	}
	return "", false
}

// str reads a string field of a JSON object, "" when absent or not a string.
func str(object map[string]any, key string) string {
	value, _ := object[key].(string)
	return value
}

// obj reads a nested JSON object, nil when absent.
func obj(object map[string]any, key string) map[string]any {
	value, _ := object[key].(map[string]any)
	return value
}

// num reads a JSON number field as an int; JSON numbers decode as float64,
// and some generators write ports as strings.
func num(object map[string]any, key string) int {
	switch value := object[key].(type) {
	case float64:
		return int(value)
	case string:
		var n int
		_, _ = fmt.Sscanf(value, "%d", &n)
		return n
	}
	return 0
}
