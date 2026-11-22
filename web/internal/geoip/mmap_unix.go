//go:build unix

package geoip

import (
	"errors"
	"os"
	"syscall"
)

// mapFile maps the database read-only: 130 MB of city data stays in the page
// cache, shared and reclaimable, instead of on the Go heap.
func mapFile(f *os.File) ([]byte, func() error, error) {
	info, err := f.Stat()
	if err != nil {
		return nil, nil, err
	}
	size := info.Size()
	if size <= 0 {
		return nil, nil, errors.New("empty file")
	}
	if int64(int(size)) != size {
		return nil, nil, errors.New("file too large to map")
	}
	data, err := syscall.Mmap(int(f.Fd()), 0, int(size), syscall.PROT_READ, syscall.MAP_SHARED)
	if err != nil {
		return nil, nil, err
	}
	return data, func() error { return syscall.Munmap(data) }, nil
}
