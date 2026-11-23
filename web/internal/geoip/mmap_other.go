//go:build !unix

package geoip

import (
	"io"
	"os"
)

// mapFile reads the whole file where there is no mmap to lean on.
func mapFile(f *os.File) ([]byte, func() error, error) {
	data, err := io.ReadAll(f)
	if err != nil {
		return nil, nil, err
	}
	return data, func() error { return nil }, nil
}
