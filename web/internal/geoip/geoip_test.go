package geoip

import (
	"encoding/binary"
	"math"
	"net/netip"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

// -- a tiny MMDB writer, enough to build test databases ----------------------

type encoder struct{ b []byte }

func (e *encoder) control(kind, size int) {
	first := byte(kind << 5)
	ext := -1
	if kind > 7 {
		first = 0
		ext = kind - 7
	}
	var extra []byte
	switch {
	case size < 29:
		first |= byte(size)
	case size < 285:
		first |= 29
		extra = []byte{byte(size - 29)}
	case size < 65821:
		first |= 30
		v := size - 285
		extra = []byte{byte(v >> 8), byte(v)}
	default:
		first |= 31
		v := size - 65821
		extra = []byte{byte(v >> 16), byte(v >> 8), byte(v)}
	}
	e.b = append(e.b, first)
	if ext >= 0 {
		e.b = append(e.b, byte(ext))
	}
	e.b = append(e.b, extra...)
}

func (e *encoder) value(v any) {
	switch v := v.(type) {
	case string:
		e.control(typeString, len(v))
		e.b = append(e.b, v...)
	case float64:
		e.control(typeDouble, 8)
		e.b = binary.BigEndian.AppendUint64(e.b, math.Float64bits(v))
	case uint16:
		e.control(typeUint16, 2)
		e.b = binary.BigEndian.AppendUint16(e.b, v)
	case uint32:
		e.control(typeUint32, 4)
		e.b = binary.BigEndian.AppendUint32(e.b, v)
	case uint64:
		e.control(typeUint64, 8)
		e.b = binary.BigEndian.AppendUint64(e.b, v)
	case int32:
		e.control(typeInt32, 4)
		e.b = binary.BigEndian.AppendUint32(e.b, uint32(v))
	case bool:
		size := 0
		if v {
			size = 1
		}
		e.control(typeBool, size)
	case map[string]any:
		keys := make([]string, 0, len(v))
		for k := range v {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		e.control(typeMap, len(v))
		for _, k := range keys {
			e.value(k)
			e.value(v[k])
		}
	case []any:
		e.control(typeArray, len(v))
		for _, item := range v {
			e.value(item)
		}
	case pointerTo:
		e.pointer(uint(v))
	default:
		panic("encoder: unsupported value")
	}
}

// pointerTo marks a value to be written as a pointer to that offset.
type pointerTo uint

func (e *encoder) pointer(target uint) {
	switch {
	case target < 2048:
		e.b = append(e.b, byte(typePointer<<5)|byte(target>>8&7), byte(target))
	case target < 526336:
		t := target - 2048
		e.b = append(e.b, byte(typePointer<<5)|1<<3|byte(t>>16&7), byte(t>>8), byte(t))
	default:
		panic("test pointer too far")
	}
}

type network struct {
	prefix string
	record map[string]any
}

// buildDB writes an IPv6 MMDB holding the given networks; IPv4 networks go
// under ::/96, where real databases keep them.
func buildDB(t *testing.T, recordSize int, networks []network) []byte {
	t.Helper()
	type child struct {
		kind int // 0 empty, 1 node, 2 data
		v    int
	}
	nodes := [][2]child{{}}
	var data encoder

	for _, n := range networks {
		p := netip.MustParsePrefix(n.prefix)
		addr := p.Addr()
		bitsLen := p.Bits()
		var raw [16]byte
		if addr.Is4() {
			a := addr.As4()
			copy(raw[12:], a[:])
			bitsLen += 96
		} else {
			raw = addr.As16()
		}
		offset := len(data.b)
		data.value(n.record)

		node := 0
		for i := 0; i < bitsLen; i++ {
			bit := raw[i>>3] >> (7 - uint(i&7)) & 1
			if i == bitsLen-1 {
				nodes[node][bit] = child{kind: 2, v: offset}
				break
			}
			if nodes[node][bit].kind != 1 {
				nodes = append(nodes, [2]child{})
				nodes[node][bit] = child{kind: 1, v: len(nodes) - 1}
			}
			node = nodes[node][bit].v
		}
	}

	count := len(nodes)
	resolve := func(c child) uint32 {
		switch c.kind {
		case 1:
			return uint32(c.v)
		case 2:
			return uint32(count + 16 + c.v)
		}
		return uint32(count)
	}
	var tree []byte
	for _, n := range nodes {
		l, r := resolve(n[0]), resolve(n[1])
		switch recordSize {
		case 24:
			tree = append(tree, byte(l>>16), byte(l>>8), byte(l), byte(r>>16), byte(r>>8), byte(r))
		case 28:
			tree = append(tree, byte(l>>16), byte(l>>8), byte(l), byte(l>>20&0xF0)|byte(r>>24&0x0F), byte(r>>16), byte(r>>8), byte(r))
		case 32:
			tree = binary.BigEndian.AppendUint32(tree, l)
			tree = binary.BigEndian.AppendUint32(tree, r)
		}
	}

	var meta encoder
	meta.value(map[string]any{
		"node_count":                  uint32(count),
		"record_size":                 uint16(recordSize),
		"ip_version":                  uint16(6),
		"database_type":               "Test-City",
		"build_epoch":                 uint64(1793501546),
		"binary_format_major_version": uint16(2),
		"binary_format_minor_version": uint16(0),
		"languages":                   []any{"en"},
		"description":                 map[string]any{"en": "test"},
	})

	out := append([]byte(nil), tree...)
	out = append(out, make([]byte, 16)...)
	out = append(out, data.b...)
	out = append(out, metadataMarker...)
	return append(out, meta.b...)
}

func cityRecord(name, country string, lat, lon float64) map[string]any {
	return map[string]any{
		"city":     map[string]any{"names": map[string]any{"en": name}},
		"country":  map[string]any{"iso_code": country},
		"location": map[string]any{"latitude": lat, "longitude": lon},
	}
}

var testNetworks = []network{
	{"77.88.0.0/16", cityRecord("Moscow (Tsentralnyy administrativnyy okrug)", "RU", 55.7342, 37.5859)},
	{"46.61.0.0/17", cityRecord("Rostov-on-Don", "RU", 47.2357, 39.7015)},
	{"8.8.8.0/24", cityRecord("Mountain View", "US", 37.422, -122.085)},
	{"2a02:6b8::/32", cityRecord("Moscow", "RU", 55.7558, 37.6173)},
	// A record with a country but no coordinates is no use for a map.
	{"10.0.0.0/8", map[string]any{"country": map[string]any{"iso_code": "ZZ"}}},
}

func TestLookupAcrossRecordSizes(t *testing.T) {
	for _, size := range []int{24, 28, 32} {
		db, err := parse(buildDB(t, size, testNetworks))
		if err != nil {
			t.Fatalf("record size %d: parse: %v", size, err)
		}
		if db.Type != "Test-City" || db.Built.IsZero() {
			t.Errorf("record size %d: metadata not read: %q %v", size, db.Type, db.Built)
		}

		cases := []struct {
			ip      string
			city    string
			country string
			lat     float64
			found   bool
		}{
			{"77.88.8.8", "Moscow", "RU", 55.7342, true},
			{"::ffff:77.88.8.8", "Moscow", "RU", 55.7342, true},
			{"46.61.0.1", "Rostov-on-Don", "RU", 47.2357, true},
			{"46.61.200.1", "", "", 0, false}, // outside the /17
			{"8.8.8.8", "Mountain View", "US", 37.422, true},
			{"2a02:6b8::feed:0ff", "Moscow", "RU", 55.7558, true},
			{"1.1.1.1", "", "", 0, false},
			{"10.1.2.3", "", "", 0, false},
			{"2001:db8::1", "", "", 0, false},
		}
		for _, c := range cases {
			place, ok := db.Lookup(netip.MustParseAddr(c.ip))
			if ok != c.found {
				t.Errorf("record size %d: %s found=%v, want %v", size, c.ip, ok, c.found)
				continue
			}
			if !ok {
				continue
			}
			if place.City != c.city || place.Country != c.country || place.Lat != c.lat {
				t.Errorf("record size %d: %s = %+v, want %s %s %v", size, c.ip, place, c.city, c.country, c.lat)
			}
		}
	}
}

func TestLookupOfTheZeroAddressIsNotFound(t *testing.T) {
	db, err := parse(buildDB(t, 28, testNetworks))
	if err != nil {
		t.Fatal(err)
	}
	if _, ok := db.Lookup(netip.Addr{}); ok {
		t.Error("an invalid address found a place")
	}
	var nilDB *DB
	if _, ok := nilDB.Lookup(netip.MustParseAddr("77.88.8.8")); ok {
		t.Error("a nil database found a place")
	}
}

func TestDecoderFollowsPointersAndLongSizes(t *testing.T) {
	var e encoder
	e.value("shared") // offset 0, pointed at below
	start := len(e.b)
	long := strings.Repeat("x", 300) // needs the two-byte size form
	mid := strings.Repeat("y", 40)   // needs the one-byte size form
	e.value(map[string]any{
		"a": pointerTo(0),
		"b": long,
		"c": uint64(1) << 40,
		"d": int32(-5),
		"e": true,
		"f": []any{1.5, "two"},
		"g": mid,
	})

	value, end, err := decoder{buf: e.b}.decode(uint(start), 0)
	if err != nil {
		t.Fatal(err)
	}
	if end != uint(len(e.b)) {
		t.Errorf("decode stopped at %d of %d", end, len(e.b))
	}
	m := value.(map[string]any)
	if m["a"] != "shared" {
		t.Errorf("pointer: got %v", m["a"])
	}
	if m["b"] != long || m["g"] != mid {
		t.Error("long strings did not round-trip")
	}
	if m["c"] != uint64(1)<<40 {
		t.Errorf("uint64: got %v", m["c"])
	}
	if m["d"] != int64(-5) {
		t.Errorf("int32: got %v", m["d"])
	}
	if m["e"] != true {
		t.Errorf("bool: got %v", m["e"])
	}
	list := m["f"].([]any)
	if len(list) != 2 || list[0] != 1.5 || list[1] != "two" {
		t.Errorf("array: got %v", list)
	}
}

func TestDecoderRejectsTruncatedValues(t *testing.T) {
	var e encoder
	e.value("hello")
	if _, _, err := (decoder{buf: e.b[:3]}).decode(0, 0); err == nil {
		t.Error("a string cut short decoded without error")
	}
	if _, _, err := (decoder{buf: nil}).decode(0, 0); err == nil {
		t.Error("an empty buffer decoded without error")
	}
}

func TestParseRejectsWhatIsNotADatabase(t *testing.T) {
	if _, err := parse([]byte("definitely not a database")); err == nil {
		t.Error("garbage parsed as a database")
	}
	good := buildDB(t, 24, testNetworks)
	// Metadata that claims far more nodes than the file holds.
	var meta encoder
	meta.value(map[string]any{"node_count": uint32(1 << 30), "record_size": uint16(24), "ip_version": uint16(6)})
	bad := append(append(append([]byte(nil), good[:64]...), metadataMarker...), meta.b...)
	if _, err := parse(bad); err == nil {
		t.Error("a tree larger than the file was accepted")
	}
}

func TestOpenReadsAFileFromDisk(t *testing.T) {
	path := filepath.Join(t.TempDir(), "city.mmdb")
	if err := os.WriteFile(path, buildDB(t, 28, testNetworks), 0o600); err != nil {
		t.Fatal(err)
	}
	db, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	if place, ok := db.Lookup(netip.MustParseAddr("77.88.8.8")); !ok || place.City != "Moscow" {
		t.Errorf("lookup through Open: %+v %v", place, ok)
	}
	if _, err := Open(filepath.Join(t.TempDir(), "missing.mmdb")); err == nil {
		t.Error("a missing file opened")
	}
}

func TestCleanCityName(t *testing.T) {
	for in, want := range map[string]string{
		"Moscow (Tsentralnyy administrativnyy okrug)": "Moscow",
		"Rostov-on-Don":       "Rostov-on-Don",
		"  Kazan  ":           "Kazan",
		"Sandton (Bryanston)": "Sandton",
		"":                    "",
	} {
		if got := CleanCityName(in); got != want {
			t.Errorf("CleanCityName(%q) = %q, want %q", in, got, want)
		}
	}
}

// Runs against a real database when GEOIP_TEST_DB names one, for example the
// DB-IP City Lite file tools/geoip/update.sh fetches. Skipped otherwise.
func TestRealDatabase(t *testing.T) {
	path := os.Getenv("GEOIP_TEST_DB")
	if path == "" {
		t.Skip("GEOIP_TEST_DB not set")
	}
	db, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	for ip, country := range map[string]string{
		"77.88.8.8":          "RU",
		"2a02:6b8::feed:0ff": "RU",
		"8.8.8.8":            "US",
	} {
		place, ok := db.Lookup(netip.MustParseAddr(ip))
		if !ok || place.Country != country {
			t.Errorf("%s: %+v %v, want country %s", ip, place, ok, country)
		}
		t.Logf("%s -> %+v", ip, place)
	}
	if _, ok := db.Lookup(netip.MustParseAddr("127.0.0.1")); ok {
		t.Error("loopback found a place")
	}
}
