package app

import (
	"net/url"
	"regexp"
	"strings"
)

// Problem is something the customer can put right, said in their words: a
// heading and what to do. It is shown under the link field, or in place of
// the results when the subscription itself is the trouble.
type Problem struct {
	Title string `json:"title"`
	Text  string `json:"text"`
	// A page that puts it right, such as where to pay, and its button.
	Link     string `json:"link,omitempty"`
	LinkText string `json:"link_text,omitempty"`
}

func (p *Problem) Error() string { return p.Title + ": " + p.Text }

var (
	webLink = regexp.MustCompile(`(?i)https?://[^\s"'<>«»]+`)
	// The id the panel knows a subscription by: the last path segment.
	shortID = regexp.MustCompile(`^[A-Za-z0-9_-]{8,}$`)
)

// CleanLink finds the subscription link in what the customer pasted. A link
// rarely arrives clean: copied out of a bot message it brings words and
// quotes along, and an app's own "add" link wraps it -- happ://add/https://...,
// sometimes percent-encoded. domains are the hosts a subscription may be on;
// none accepts any host, for a build made without them.
func CleanLink(pasted string, domains []string) (string, *Problem) {
	text := strings.TrimSpace(pasted)
	if text == "" {
		return "", &Problem{Title: "Вставьте ссылку", Text: "Ссылка подписки есть в боте и в личном кабинете на сайте."}
	}
	if strings.Contains(strings.ToLower(text), "%3a%2f%2f") {
		if decoded, err := url.QueryUnescape(text); err == nil {
			text = decoded
		}
	}
	found := webLink.FindString(text)
	if found == "" {
		lower := strings.ToLower(text)
		switch {
		case strings.HasPrefix(lower, "happ://crypt"):
			return "", &Problem{Title: "Это зашифрованная ссылка Happ",
				Text: "Из неё не достать адрес подписки. Скопируйте обычную ссылку подписки в боте или личном кабинете."}
		case strings.Contains(lower, "://"):
			return "", &Problem{Title: "Это ссылка на один сервер",
				Text: "Нужна ссылка на всю подписку: она начинается с https://. Скопируйте её в боте или личном кабинете."}
		}
		return "", &Problem{Title: "Это не ссылка", Text: "Скопируйте ссылку подписки в боте или личном кабинете целиком и вставьте сюда."}
	}
	found = strings.TrimRight(found, ".,;:!?)]}")

	u, err := url.Parse(found)
	if err != nil || u.Host == "" {
		return "", &Problem{Title: "Ссылка скопировалась не целиком", Text: "Скопируйте её в боте или личном кабинете ещё раз."}
	}
	u.Fragment, u.RawFragment = "", ""
	host := strings.ToLower(u.Hostname())
	if len(domains) > 0 {
		ours := false
		for _, domain := range domains {
			ours = ours || host == strings.ToLower(domain)
		}
		if !ours {
			return "", &Problem{Title: "Это ссылка не на нашу подписку",
				Text: "Ссылка ведёт на " + host + ", а подписка начинается с https://" + domains[0] + "/. Скопируйте её в боте или личном кабинете."}
		}
		u.Scheme = "https"
	}
	segments := strings.Split(strings.Trim(u.Path, "/"), "/")
	if !shortID.MatchString(segments[len(segments)-1]) {
		return "", &Problem{Title: "Ссылка скопировалась не целиком",
			Text: "В конце ссылки должен быть код подписки из букв и цифр. Скопируйте её в боте или личном кабинете ещё раз."}
	}
	return u.String(), nil
}
