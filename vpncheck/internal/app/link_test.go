package app

import "testing"

func TestCleanLink(t *testing.T) {
	domains := []string{"sub.example.com"}
	const good = "https://sub.example.com/SayZcYcdx7zRHfxe"
	cases := []struct {
		name, pasted, want, problem string
	}{
		{"plain", good, good, ""},
		{"spaces and quotes", "  «" + good + "»\n", good, ""},
		{"inside a bot message", "Ваша ссылка: " + good + ". Скопируйте её в Happ", good, ""},
		{"happ add link", "happ://add/" + good, good, ""},
		{"percent-encoded", "happ://add/https%3A%2F%2Fsub.example.com%2FSayZcYcdx7zRHfxe", good, ""},
		{"fragment dropped", good + "#KairaVPN", good, ""},
		{"api path", "https://sub.example.com/api/sub/SayZcYcdx7zRHfxe", "https://sub.example.com/api/sub/SayZcYcdx7zRHfxe", ""},
		{"http made https", "http://sub.example.com/SayZcYcdx7zRHfxe", good, ""},
		{"host in capitals", "https://SUB.example.com/SayZcYcdx7zRHfxe", "https://SUB.example.com/SayZcYcdx7zRHfxe", ""},
		{"empty", "  ", "", "Вставьте ссылку"},
		{"words", "не работает vpn", "", "Это не ссылка"},
		{"one server", "vless://uuid@de1.example.com:443?security=reality#de1", "", "Это ссылка на один сервер"},
		{"encrypted happ", "happ://crypt3/AbCdEf", "", "Это зашифрованная ссылка Happ"},
		{"other host", "https://evil.example.net/SayZcYcdx7zRHfxe", "", "Это ссылка не на нашу подписку"},
		{"cut short", "https://sub.example.com/SayZ", "", "Ссылка скопировалась не целиком"},
		{"no id", "https://sub.example.com/", "", "Ссылка скопировалась не целиком"},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			got, problem := CleanLink(c.pasted, domains)
			if c.problem != "" {
				if problem == nil || problem.Title != c.problem {
					t.Fatalf("got %q, %v; want problem %q", got, problem, c.problem)
				}
				return
			}
			if problem != nil || got != c.want {
				t.Fatalf("got %q, %v; want %q", got, problem, c.want)
			}
		})
	}
}

func TestCleanLinkWithoutDomains(t *testing.T) {
	// A build without domains (a test, a local run) takes any host, http too.
	got, problem := CleanLink("http://127.0.0.1:8080/sub/SayZcYcdx7zRHfxe", nil)
	if problem != nil || got != "http://127.0.0.1:8080/sub/SayZcYcdx7zRHfxe" {
		t.Fatalf("got %q, %v", got, problem)
	}
}
