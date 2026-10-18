package check

import (
	"fmt"
	"regexp"
	"slices"
	"strings"
)

var certValidFor = regexp.MustCompile(`certificate is valid for ([^,]+(?:, [^,]+)*?), not (\S+)`)

// hints turns what the stages saw into what to do about it.
//
// Every rule here is a failure this project has already had to work out by
// hand from a customer's client log. The raw error always goes into the
// report as well: a hint is a reading of it, not a replacement.
func hints(r *Result) []string {
	var out []string
	add := func(format string, args ...any) {
		text := fmt.Sprintf(format, args...)
		if !slices.Contains(out, text) {
			out = append(out, text)
		}
	}
	t := r.Target
	cause := strings.ToLower(r.Cause)
	log := strings.ToLower(strings.Join(r.Log, "\n"))
	dns, tcp, tls, ping := r.step(StepDNS), r.step(StepTCP), r.step(StepTLS), r.step(StepPing)
	pingOK := ping != nil && ping.Status != Fail

	if dns != nil && dns.Status == Fail {
		if len(r.ips) > 0 {
			add("Системный DNS не находит %s, а публичные DNS находят: сбой у DNS провайдера или в настройках сети. "+
				"Клиент без своего DNS-сервера к этому серверу не подключится.", t.Address)
		} else {
			add("Имя %s не находится ни одним DNS: проверьте A-запись домена.", t.Address)
		}
	}
	if dns != nil && dns.Status == Warn {
		add("Системный DNS вернул для %s другие адреса, чем 77.88.8.8 и 1.1.1.1: провайдер может подменять ответы.", t.Address)
	}

	if tcp != nil && tcp.Status == Fail {
		switch r.tcpKind {
		case kindRefused:
			add("На %s никто не принимает соединения: inbound не запущен на ноде, не назначен ей в панели, "+
				"или в хосте указан не тот порт.", t.Endpoint())
		case kindReset:
			add("Соединение с %s сбрасывается сразу: похоже на блокировку по пути.", t.Endpoint())
		default:
			add("%s не отвечает: сервер выключен, порт закрыт файрволом или адрес блокируется по пути. "+
				"Если с сервера вне РФ этот же хост работает — это блокировка.", t.Endpoint())
		}
	}

	if tls != nil && tls.Status == Fail && t.Security == "reality" {
		if r.tlsKind == kindReset {
			add("Рукопожатие с SNI %s сбрасывается: похоже на блокировку по SNI.", t.SNI)
		} else {
			add("Порт открыт, но TLS-рукопожатие с SNI %s не завершается: нода не достаёт до сайта-маски (target) "+
				"Reality, или рукопожатие режется по пути.", t.SNI)
		}
	}
	if tls != nil && tls.Status == Warn && t.Security == "tls" && len(r.certNames) > 0 {
		add("Сертификат на %s выписан на %s, а клиент ждёт %s.", t.Endpoint(), strings.Join(r.certNames, ", "), t.SNI)
	}
	if t.Security == "reality" && (r.curve == "P256" || r.curve == "P384" || r.curve == "P521") {
		add("Сайт-маска %s выбирает %s. С fingerprint firefox или random клиент на это отвечает «invalid server key share» — "+
			"нужен target с X25519 или fingerprint chrome.", t.SNI, r.curve)
	}

	switch {
	case strings.Contains(cause, "invalid server key share"):
		add("Сайт-маска %s выбрал ключ, которого fingerprint «%s» не предлагал (обычно P-256): смените target "+
			"на сайт с X25519 или fingerprint на chrome.", t.SNI, t.Fingerprint)
	case certValidFor.MatchString(r.Cause):
		match := certValidFor.FindStringSubmatch(r.Cause)
		add("Сертификат сервера выписан на %s, а клиент проверяет %s: в хосте указан не тот SNI (serverName).", match[1], match[2])
	case strings.Contains(cause, "processed invalid connection") || strings.Contains(log, "received real certificate") ||
		// A REALITY client only ever checks a certificate the CA way when
		// the server has passed it through to the mask site.
		(t.Security == "reality" && strings.Contains(cause, "x509:")):
		add("Сервер не узнал клиента и ответил сертификатом сайта-маски: publicKey или shortId хоста не совпадают " +
			"с ключами inbound на ноде, либо SNI не входит в его serverNames.")
	case strings.Contains(cause, "certificate is expired") || strings.Contains(cause, "certificate has expired"):
		add("Сертификат на %s просрочен: на ноде не сработало автопродление. Клиенты, которые проверяют "+
			"сертификат, к этому серверу не подключатся.", t.Endpoint())
	case strings.Contains(cause, "connection refused") && (tcp == nil || tcp.Status != Fail):
		add("Сервер отклонил соединение (connection refused) уже внутри протокола: за %s никто не слушает "+
			"тот порт, куда его передают (например, nginx отдаёт на порт, где нет inbound).", t.Endpoint())
	case strings.Contains(cause, "auth failed"):
		add("Сервер ответил, но не принял пароль: нода не знает этого пользователя на %s — он не назначен на inbound "+
			"(сквад) или подписка устарела.", t.Endpoint())
	case !pingOK && t.UDP:
		add("Сервер не ответил по UDP на порт %d: UDP/QUIC к зарубежным адресам часто режут, особенно в мобильных "+
			"сетях. Если TCP-профили работают — дело в этом.", t.Port)
	case !pingOK && tcp != nil && tcp.Status == OK && strings.HasSuffix(cause, "eof"):
		add("Сервер принял соединение и сразу закрыл его. Обычно это значит, что нода не знает этого пользователя " +
			"(он не назначен на inbound — сквад, или подписка устарела), либо у самой ноды нет выхода в интернет.")
	case !pingOK && tcp != nil && tcp.Status == OK && (tls == nil || tls.Status != Fail):
		add("Порт отвечает, но через протокол ответа нет. Подробности — в логе Xray этого сервера.")
	}

	if pingOK {
		for _, step := range r.Steps {
			if step.Status != Fail && step.Status != Warn {
				continue
			}
			switch step.Name {
			case "Telegram":
				add("Туннель работает, но Telegram через этот сервер не открывается.")
			case "Google":
				add("Туннель работает, но Google через этот сервер не открывается.")
			case StepExit:
				add("Туннель работает, но Cloudflare через этот сервер не отвечает.")
			case StepPing:
				add("Проверочный адрес отвечает не так, как обычно: подробности в шаге «%s».", StepPing)
			}
		}
	}
	return out
}
