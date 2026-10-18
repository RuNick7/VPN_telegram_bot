package subscription

import (
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/url"
	"strconv"
	"strings"
)

// LinkToOutbound turns one share link into the Xray outbound it describes,
// and returns the name after `#`.
//
// Only the fallback path: Happ is given JSON configs, which carry every
// setting as is. Links are what other apps get, and what a panel answers with
// when asked as an unknown client, so they are read well enough to connect.
func LinkToOutbound(link string) (map[string]any, string, error) {
	scheme, _, _ := strings.Cut(link, "://")
	var build func(string) (map[string]any, string, error)
	switch strings.ToLower(scheme) {
	case "vless":
		build = func(link string) (map[string]any, string, error) { return vlessOrTrojan(link, "vless") }
	case "trojan":
		build = func(link string) (map[string]any, string, error) { return vlessOrTrojan(link, "trojan") }
	case "hysteria2", "hy2":
		build = hysteria2
	case "ss":
		build = shadowsocks
	case "vmess":
		build = vmess
	default:
		return nil, "", fmt.Errorf("протокол %q не поддерживается", scheme)
	}
	outbound, name, err := build(link)
	if err != nil {
		return nil, "", err
	}
	// Into the shape a JSON subscription decodes to -- float64 numbers, []any
	// lists -- so everything downstream reads one shape, not two.
	data, _ := json.Marshal(outbound)
	var decoded map[string]any
	if err := json.Unmarshal(data, &decoded); err != nil {
		return nil, "", err
	}
	return decoded, name, nil
}

func vlessOrTrojan(link, protocol string) (map[string]any, string, error) {
	u, err := url.Parse(link)
	if err != nil {
		return nil, "", fmt.Errorf("%s: %w", protocol, err)
	}
	host, port, err := hostPort(u)
	if err != nil {
		return nil, "", fmt.Errorf("%s: %w", protocol, err)
	}
	secret := u.User.Username()
	q := u.Query()

	settings := map[string]any{"address": host, "port": port}
	if protocol == "vless" {
		settings["id"] = secret
		settings["encryption"] = orDefault(q.Get("encryption"), "none")
		if flow := q.Get("flow"); flow != "" {
			settings["flow"] = flow
		}
	} else {
		settings["password"] = secret
	}
	defaultSecurity := "none"
	if protocol == "trojan" {
		defaultSecurity = "tls"
	}
	return map[string]any{
		"protocol":       protocol,
		"settings":       settings,
		"streamSettings": streamFromQuery(q, defaultSecurity),
	}, fragment(u), nil
}

// streamFromQuery reads the transport and security of a vless:// or
// trojan:// link -- the parameter names Xray's share-link standard uses.
func streamFromQuery(q url.Values, defaultSecurity string) map[string]any {
	network := orDefault(q.Get("type"), "tcp")
	stream := map[string]any{"network": network}
	path, host := q.Get("path"), q.Get("host")

	switch network {
	case "grpc":
		grpc := map[string]any{"serviceName": q.Get("serviceName"), "multiMode": q.Get("mode") == "multi"}
		if authority := q.Get("authority"); authority != "" {
			grpc["authority"] = authority
		}
		stream["grpcSettings"] = grpc
	case "ws":
		stream["wsSettings"] = map[string]any{"path": path, "host": host}
	case "httpupgrade":
		stream["httpupgradeSettings"] = map[string]any{"path": path, "host": host}
	case "xhttp", "splithttp":
		xhttp := map[string]any{"path": path, "host": host, "mode": orDefault(q.Get("mode"), "auto")}
		if extra := q.Get("extra"); extra != "" {
			var parsed map[string]any
			if json.Unmarshal([]byte(extra), &parsed) == nil {
				xhttp["extra"] = parsed
			}
		}
		stream["network"] = "xhttp"
		stream["xhttpSettings"] = xhttp
	case "tcp", "raw":
		if q.Get("headerType") == "http" {
			stream["rawSettings"] = map[string]any{"header": map[string]any{
				"type":    "http",
				"request": map[string]any{"path": []string{orDefault(path, "/")}, "headers": map[string]any{"Host": strings.Split(host, ",")}},
			}}
		}
	case "kcp":
		kcp := map[string]any{"header": map[string]any{"type": orDefault(q.Get("headerType"), "none")}}
		if seed := q.Get("seed"); seed != "" {
			kcp["seed"] = seed
		}
		stream["kcpSettings"] = kcp
	}

	security := orDefault(q.Get("security"), defaultSecurity)
	stream["security"] = security
	switch security {
	case "tls":
		tls := map[string]any{"serverName": q.Get("sni"), "fingerprint": q.Get("fp")}
		if alpn := q.Get("alpn"); alpn != "" {
			tls["alpn"] = strings.Split(alpn, ",")
		}
		pinning(tls, q)
		if ech := q.Get("ech"); ech != "" {
			tls["echConfigList"] = ech
		}
		stream["tlsSettings"] = tls
	case "reality":
		reality := map[string]any{
			"serverName":  q.Get("sni"),
			"fingerprint": orDefault(q.Get("fp"), "chrome"),
			"publicKey":   q.Get("pbk"),
			"shortId":     q.Get("sid"),
			"spiderX":     q.Get("spx"),
		}
		if verify := q.Get("pqv"); verify != "" {
			reality["mldsa65Verify"] = verify
		}
		stream["realitySettings"] = reality
	}
	return stream
}

// pinning carries over how a link pins the server's certificate. Xray 26
// refuses "allowInsecure" outright, so insecure=1 is dropped rather than
// mapped: a server that depends on it fails here exactly as in the app.
func pinning(tls map[string]any, q url.Values) {
	if pcs := q.Get("pcs"); pcs != "" {
		tls["pinnedPeerCertSha256"] = pcs
	}
	if vcn := q.Get("vcn"); vcn != "" {
		tls["verifyPeerCertByName"] = vcn
	}
}

func hysteria2(link string) (map[string]any, string, error) {
	u, err := url.Parse(link)
	if err != nil {
		return nil, "", fmt.Errorf("hysteria2: %w", err)
	}
	host, port, err := hostPort(u)
	if err != nil {
		return nil, "", fmt.Errorf("hysteria2: %w", err)
	}
	auth := u.User.Username()
	if password, ok := u.User.Password(); ok {
		auth += ":" + password
	}
	q := u.Query()
	tls := map[string]any{"serverName": orDefault(q.Get("sni"), host), "alpn": []string{"h3"}}
	pinning(tls, q)
	if pin := q.Get("pinSHA256"); pin != "" {
		tls["pinnedPeerCertSha256"] = pin
	}
	stream := map[string]any{
		"network":          "hysteria",
		"hysteriaSettings": map[string]any{"version": 2, "auth": auth},
		"security":         "tls",
		"tlsSettings":      tls,
	}
	if q.Get("obfs") == "salamander" {
		stream["finalmask"] = map[string]any{"udp": []any{
			map[string]any{"type": "salamander", "settings": map[string]any{"password": q.Get("obfs-password")}},
		}}
	}
	return map[string]any{
		"protocol":       "hysteria",
		"settings":       map[string]any{"version": 2, "address": host, "port": port},
		"streamSettings": stream,
	}, fragment(u), nil
}

// shadowsocks reads both spellings: SIP002 (`ss://base64(method:password)@host:port`)
// and the older one with everything inside the base64.
func shadowsocks(link string) (map[string]any, string, error) {
	rest := strings.TrimPrefix(link, link[:strings.Index(link, "://")+3])
	name := ""
	if before, after, ok := strings.Cut(rest, "#"); ok {
		rest = before
		name, _ = url.PathUnescape(after)
	}
	rest, _, _ = strings.Cut(rest, "?")

	userinfo, server, ok := strings.Cut(rest, "@")
	if !ok {
		decoded, ok := decodeBase64(rest)
		if !ok {
			return nil, "", errors.New("ss: ссылка не читается")
		}
		userinfo, server, ok = strings.Cut(decoded, "@")
		if !ok {
			return nil, "", errors.New("ss: нет адреса сервера")
		}
	} else if decoded, ok := decodeBase64(userinfo); ok && strings.Contains(decoded, ":") {
		userinfo = decoded
	} else if unescaped, err := url.PathUnescape(userinfo); err == nil {
		userinfo = unescaped
	}
	method, password, ok := strings.Cut(userinfo, ":")
	if !ok {
		return nil, "", errors.New("ss: нет метода шифрования")
	}
	host, portText, err := net.SplitHostPort(server)
	if err != nil {
		return nil, "", fmt.Errorf("ss: %w", err)
	}
	port, err := strconv.Atoi(portText)
	if err != nil {
		return nil, "", fmt.Errorf("ss: порт %q", portText)
	}
	return map[string]any{
		"protocol": "shadowsocks",
		"settings": map[string]any{"address": host, "port": port, "method": method, "password": password},
	}, name, nil
}

func vmess(link string) (map[string]any, string, error) {
	decoded, ok := decodeBase64(strings.TrimPrefix(link, link[:strings.Index(link, "://")+3]))
	if !ok {
		return nil, "", errors.New("vmess: ссылка не читается")
	}
	var v map[string]any
	if err := json.Unmarshal([]byte(decoded), &v); err != nil {
		return nil, "", fmt.Errorf("vmess: %w", err)
	}
	q := url.Values{}
	q.Set("type", orDefault(str(v, "net"), "tcp"))
	q.Set("security", orDefault(str(v, "tls"), "none"))
	for from, to := range map[string]string{
		"host": "host", "path": "path", "sni": "sni", "alpn": "alpn", "fp": "fp", "type": "headerType",
	} {
		if value := str(v, from); value != "" {
			q.Set(to, value)
		}
	}
	if q.Get("type") == "grpc" {
		q.Set("serviceName", str(v, "path"))
	}
	return map[string]any{
		"protocol": "vmess",
		"settings": map[string]any{"vnext": []any{map[string]any{
			"address": str(v, "add"),
			"port":    num(v, "port"),
			"users":   []any{map[string]any{"id": str(v, "id"), "security": orDefault(str(v, "scy"), "auto")}},
		}}},
		"streamSettings": streamFromQuery(q, "none"),
	}, str(v, "ps"), nil
}

func hostPort(u *url.URL) (string, int, error) {
	host := u.Hostname()
	if host == "" {
		return "", 0, errors.New("нет адреса сервера")
	}
	port, err := strconv.Atoi(u.Port())
	if err != nil || port <= 0 || port > 65535 {
		return "", 0, fmt.Errorf("неверный порт %q", u.Port())
	}
	return host, port, nil
}

func fragment(u *url.URL) string {
	if u.Fragment != "" {
		return u.Fragment
	}
	return u.Host
}

func orDefault(value, fallback string) string {
	if value == "" {
		return fallback
	}
	return value
}
