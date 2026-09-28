package support

import (
	"context"
	"errors"
	"io"
)

// Fetch returns up to n bytes of a stored file, starting at offset.
type Fetch func(ctx context.Context, offset, n int64) ([]byte, error)

// blobWindow is how much of a file one query brings back.
const blobWindow = 1 << 20

// Blob reads a stored file a window at a time, as an io.ReadSeeker.
//
// That is what lets http.ServeContent answer byte ranges without the whole
// file in memory. A video player asks for a file in several ranges -- Safari
// will not play one at all from a server that cannot answer them -- and
// loading a 45 MB recording from Postgres once per range would turn one
// viewing into a few hundred megabytes of reads. With the column stored
// uncompressed (see migration 0015), a slice costs what the slice weighs.
type Blob struct {
	ctx    context.Context
	fetch  Fetch
	size   int64
	offset int64

	window   []byte
	windowAt int64
}

// NewBlob reads a file of the given size through fetch.
func NewBlob(ctx context.Context, size int64, fetch Fetch) *Blob {
	return &Blob{ctx: ctx, fetch: fetch, size: size}
}

func (b *Blob) Read(p []byte) (int, error) {
	if b.offset >= b.size {
		return 0, io.EOF
	}
	if len(p) == 0 {
		return 0, nil
	}
	if b.offset < b.windowAt || b.offset >= b.windowAt+int64(len(b.window)) {
		chunk, err := b.fetch(b.ctx, b.offset, min(blobWindow, b.size-b.offset))
		if err != nil {
			return 0, err
		}
		if len(chunk) == 0 {
			// Shorter than its recorded size. Saying EOF would hand the
			// client a truncated file with a success status.
			return 0, io.ErrUnexpectedEOF
		}
		b.window, b.windowAt = chunk, b.offset
	}
	n := copy(p, b.window[b.offset-b.windowAt:])
	b.offset += int64(n)
	return n, nil
}

func (b *Blob) Seek(offset int64, whence int) (int64, error) {
	var position int64
	switch whence {
	case io.SeekStart:
		position = offset
	case io.SeekCurrent:
		position = b.offset + offset
	case io.SeekEnd:
		position = b.size + offset
	default:
		return 0, errors.New("blob: invalid whence")
	}
	if position < 0 {
		return 0, errors.New("blob: negative position")
	}
	b.offset = position
	return position, nil
}
