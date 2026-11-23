// Package geoip says roughly where an IP address is: a city and its
// coordinates, from a MaxMind-format (MMDB) city database. The site uses it to
// start the landing page's planet from the visitor's own city.
//
// Written against the format rather than imported: the reader is a binary
// search tree walk and a small value decoder, a few hundred lines with the
// standard library, and the database is DB-IP's free "IP to City Lite"
// (CC BY 4.0 -- the page credits it), published monthly at
// https://db-ip.com/db/download/ip-to-city-lite as an .mmdb file.
//
// Nothing here is used to decide anything about a request. The answer only
// chooses where a comet starts from on a picture.
package geoip

import (
	"bytes"
	"errors"
	"fmt"
	"net/netip"
	"os"
	"strings"
	"time"
)

// Place is what the page needs: a name to show and where to draw the dot.
type Place struct {
	City    string  `json:"city"`    // English name, district suffix dropped
	Country string  `json:"country"` // ISO 3166-1 alpha-2
	Lat     float64 `json:"lat"`
	Lon     float64 `json:"lon"`
}

// DB is an open city database. Safe for concurrent lookups.
type DB struct {
	data      []byte
	release   func() error
	nodeCount uint
	recSize   uint
	treeSize  uint
	ipVersion uint
	ipv4Start uint

	Type  string
	Built time.Time
}

var metadataMarker = []byte("\xab\xcd\xefMaxMind.com")

// Open maps the database file into memory and reads its metadata.
func Open(path string) (*DB, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, release, err := mapFile(f)
	if err != nil {
		return nil, fmt.Errorf("geoip: map %s: %w", path, err)
	}
	db, err := parse(data)
	if err != nil {
		_ = release()
		return nil, fmt.Errorf("geoip: %s: %w", path, err)
	}
	db.release = release
	return db, nil
}

// parse reads the metadata at the end of an MMDB image and prepares lookups.
func parse(data []byte) (*DB, error) {
	// The metadata block follows the last marker, within the last 128 KiB.
	tail := 128 * 1024
	from := 0
	if len(data) > tail {
		from = len(data) - tail
	}
	at := bytes.LastIndex(data[from:], metadataMarker)
	if at < 0 {
		return nil, errors.New("no MaxMind metadata marker: not an MMDB file")
	}
	metaStart := uint(from + at + len(metadataMarker))
	meta, _, err := decoder{buf: data, base: metaStart}.decode(metaStart, 0)
	if err != nil {
		return nil, fmt.Errorf("metadata: %w", err)
	}
	m, ok := meta.(map[string]any)
	if !ok {
		return nil, errors.New("metadata is not a map")
	}
	db := &DB{data: data}
	db.nodeCount = uintField(m, "node_count")
	db.recSize = uintField(m, "record_size")
	db.ipVersion = uintField(m, "ip_version")
	db.Type, _ = m["database_type"].(string)
	if epoch := uintField(m, "build_epoch"); epoch > 0 {
		db.Built = time.Unix(int64(epoch), 0).UTC()
	}
	switch db.recSize {
	case 24, 28, 32:
	default:
		return nil, fmt.Errorf("unsupported record size %d", db.recSize)
	}
	if db.ipVersion != 4 && db.ipVersion != 6 {
		return nil, fmt.Errorf("unsupported ip_version %d", db.ipVersion)
	}
	db.treeSize = db.nodeCount * db.recSize / 4 // two records per node, recSize bits each
	if db.nodeCount == 0 || db.treeSize+16 > metaStart {
		return nil, errors.New("search tree does not fit the file")
	}

	// In an IPv6 database the IPv4 space lives under ::/96, so every IPv4
	// lookup starts 96 left turns down the tree.
	if db.ipVersion == 6 {
		node := uint(0)
		for i := 0; i < 96 && node < db.nodeCount; i++ {
			if node, err = db.record(node, 0); err != nil {
				return nil, err
			}
		}
		db.ipv4Start = node
	}
	return db, nil
}

// Close releases the mapping. Lookups after Close panic.
func (db *DB) Close() error {
	if db == nil || db.release == nil {
		return nil
	}
	release := db.release
	db.release = nil
	db.data = nil
	return release()
}

// Lookup returns the place for an address, and false when the database has
// no city-level answer for it (unknown, or a record without coordinates).
func (db *DB) Lookup(ip netip.Addr) (Place, bool) {
	record, ok, err := db.Record(ip)
	if err != nil || !ok {
		return Place{}, false
	}
	return placeFrom(record)
}

// Record returns the raw decoded record for an address.
func (db *DB) Record(ip netip.Addr) (map[string]any, bool, error) {
	if db == nil || !ip.IsValid() {
		return nil, false, nil
	}
	ip = ip.Unmap()
	var bits []byte
	node := uint(0)
	if ip.Is4() {
		a := ip.As4()
		bits = a[:]
		if db.ipVersion == 6 {
			node = db.ipv4Start
		}
	} else {
		if db.ipVersion == 4 {
			return nil, false, nil
		}
		a := ip.As16()
		bits = a[:]
	}

	var err error
	for i := 0; i < len(bits)*8 && node < db.nodeCount; i++ {
		bit := (bits[i>>3] >> (7 - uint(i&7))) & 1
		if node, err = db.record(node, bit); err != nil {
			return nil, false, err
		}
	}
	if node <= db.nodeCount {
		// Equal to node_count means "no data"; below it means the address ran
		// out of bits inside the tree, which a well-formed file never does.
		return nil, false, nil
	}

	// A data record: its offset counts from the start of the search tree's
	// 16-byte separator, so node_count + 16 is the first byte of data.
	offset := db.treeSize + (node - db.nodeCount)
	value, _, err := decoder{buf: db.data, base: db.treeSize + 16}.decode(offset, 0)
	if err != nil {
		return nil, false, err
	}
	m, ok := value.(map[string]any)
	return m, ok, nil
}

// record reads the left (bit 0) or right (bit 1) pointer of a tree node.
func (db *DB) record(node uint, bit byte) (uint, error) {
	size := db.recSize / 4 // bytes per node
	start := node * size
	if start+size > db.treeSize {
		return 0, errors.New("tree node out of range")
	}
	b := db.data[start : start+size]
	switch db.recSize {
	case 24:
		if bit == 1 {
			b = b[3:]
		}
		return uint(b[0])<<16 | uint(b[1])<<8 | uint(b[2]), nil
	case 28:
		if bit == 0 {
			return uint(b[3]&0xF0)<<20 | uint(b[0])<<16 | uint(b[1])<<8 | uint(b[2]), nil
		}
		return uint(b[3]&0x0F)<<24 | uint(b[4])<<16 | uint(b[5])<<8 | uint(b[6]), nil
	default: // 32
		if bit == 1 {
			b = b[4:]
		}
		return uint(b[0])<<24 | uint(b[1])<<16 | uint(b[2])<<8 | uint(b[3]), nil
	}
}

// placeFrom picks the city fields out of a GeoIP2-City-shaped record.
func placeFrom(record map[string]any) (Place, bool) {
	location, _ := record["location"].(map[string]any)
	lat, okLat := location["latitude"].(float64)
	lon, okLon := location["longitude"].(float64)
	if !okLat || !okLon {
		return Place{}, false
	}
	place := Place{Lat: lat, Lon: lon}
	if city, ok := record["city"].(map[string]any); ok {
		if names, ok := city["names"].(map[string]any); ok {
			name, _ := names["en"].(string)
			place.City = CleanCityName(name)
		}
	}
	if country, ok := record["country"].(map[string]any); ok {
		place.Country, _ = country["iso_code"].(string)
	}
	return place, true
}

// CleanCityName drops the district DB-IP appends to some city names:
// "Moscow (Tsentralnyy administrativnyy okrug)" is Moscow to a visitor.
func CleanCityName(name string) string {
	if cut, _, ok := strings.Cut(name, " ("); ok {
		name = cut
	}
	return strings.TrimSpace(name)
}

func uintField(m map[string]any, key string) uint {
	switch v := m[key].(type) {
	case uint64:
		return uint(v)
	case int64:
		if v > 0 {
			return uint(v)
		}
	}
	return 0
}
