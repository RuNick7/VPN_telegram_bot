package phone

import (
	"context"
	"encoding/binary"
	"net"
	"os"
	"path/filepath"
	"reflect"
	"testing"
	"time"

	"github.com/RuNick7/vpn-check/internal/check"
)

func TestRead(t *testing.T) {
	path := filepath.Join(t.TempDir(), "network")
	if got := Read(path); !reflect.DeepEqual(got, Network{}) {
		t.Errorf("no file: %+v", got)
	}
	data := "network=мобильная сеть, MegaFon\nmetered=1\nvpn=0\ndns=10.0.0.1, fe80::1%wlan0,\nрусский текст без знака\n"
	if err := os.WriteFile(path, []byte(data), 0o600); err != nil {
		t.Fatal(err)
	}
	want := Network{Name: "мобильная сеть, MegaFon", Metered: true, DNS: []string{"10.0.0.1", "fe80::1%wlan0"}}
	if got := Read(path); !reflect.DeepEqual(got, want) {
		t.Errorf("got %+v, want %+v", got, want)
	}
}

// The system resolver asks the servers the file names, as they change, and
// the check hears of a VPN from the file too.
func TestUse(t *testing.T) {
	dns := fakeDNS(t, net.IPv4(192, 0, 2, 7))
	path := filepath.Join(t.TempDir(), "network")
	write := func(data string) {
		t.Helper()
		if err := os.WriteFile(path, []byte(data), 0o600); err != nil {
			t.Fatal(err)
		}
	}
	write("network=Wi-Fi\nvpn=1\ndns=" + dns + "\n")
	Use(path)
	t.Cleanup(func() {
		net.DefaultResolver.PreferGo, net.DefaultResolver.Dial = false, nil
		check.SystemVPN, check.SystemNetwork = nil, nil
	})

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	ips, err := net.DefaultResolver.LookupIP(ctx, "ip4", "node.example.test")
	if err != nil || len(ips) != 1 || !ips[0].Equal(net.IPv4(192, 0, 2, 7)) {
		t.Fatalf("lookup: %v, %v", ips, err)
	}
	if check.ActiveTunnel() != "VPN" || check.SystemNetwork() != "Wi-Fi" {
		t.Errorf("tunnel %q, network %q", check.ActiveTunnel(), check.SystemNetwork())
	}
	write("network=Wi-Fi\nvpn=0\ndns=" + dns + "\n")
	if name := check.ActiveTunnel(); name != "" {
		t.Errorf("VPN switched off, still %q", name)
	}
}

// fakeDNS answers every A question with ip and every other with nothing,
// on a port of 127.0.0.1, which it returns as host:port.
func fakeDNS(t *testing.T, ip net.IP) string {
	conn, err := net.ListenPacket("udp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { conn.Close() })
	go func() {
		buf := make([]byte, 512)
		for {
			n, from, err := conn.ReadFrom(buf)
			if err != nil {
				return
			}
			query := buf[:n]
			// Past the header and the question's name to its type.
			end := 12
			for end < n && query[end] != 0 {
				end += int(query[end]) + 1
			}
			if end+5 > n {
				continue
			}
			answer := append([]byte(nil), query[:end+5]...)
			answer[2] |= 0x80 // a response
			answer[3] = 0x80  // recursion available, no error
			if binary.BigEndian.Uint16(query[end+1:]) == 1 {
				binary.BigEndian.PutUint16(answer[6:], 1)
				answer = append(answer, 0xc0, 12, 0, 1, 0, 1, 0, 0, 0, 60, 0, 4)
				answer = append(answer, ip.To4()...)
			}
			_, _ = conn.WriteTo(answer, from)
		}
	}()
	return conn.LocalAddr().String()
}
