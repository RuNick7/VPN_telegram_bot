package geoip

import (
	"encoding/binary"
	"errors"
	"fmt"
	"math"
)

// The MMDB data section format: every value starts with a control byte whose
// top three bits are its type (0 means "extended": the type is 7 plus the
// next byte) and whose low five bits are its size, with 29, 30 and 31 meaning
// the size continues in the next one, two or three bytes. Pointers are the
// exception: their size bits encode the pointer itself.
const (
	typeExtended  = 0
	typePointer   = 1
	typeString    = 2
	typeDouble    = 3
	typeBytes     = 4
	typeUint16    = 5
	typeUint32    = 6
	typeMap       = 7
	typeInt32     = 8
	typeUint64    = 9
	typeUint128   = 10
	typeArray     = 11
	typeContainer = 12
	typeEnd       = 13
	typeBool      = 14
	typeFloat     = 15
)

// maxDepth bounds nesting, so a damaged or hostile file cannot recurse the
// decoder off the stack.
const maxDepth = 32

var errTruncated = errors.New("geoip: value runs past the end of the file")

type decoder struct {
	buf  []byte
	base uint // pointers count from here: the data section, or the metadata
}

// decode reads one value at off and returns it with the offset just past it.
// Values come back as string, float64, []byte, uint64, int64, bool,
// map[string]any or []any.
func (d decoder) decode(off uint, depth int) (any, uint, error) {
	if depth > maxDepth {
		return nil, 0, errors.New("geoip: values nested too deeply")
	}
	ctrl, off, err := d.byteAt(off)
	if err != nil {
		return nil, 0, err
	}
	kind := uint(ctrl >> 5)

	if kind == typePointer {
		target, next, err := d.pointer(ctrl, off)
		if err != nil {
			return nil, 0, err
		}
		// A pointer's value is decoded where it points, but reading carries on
		// after the pointer itself.
		value, _, err := d.decode(d.base+target, depth+1)
		return value, next, err
	}

	if kind == typeExtended {
		var ext byte
		if ext, off, err = d.byteAt(off); err != nil {
			return nil, 0, err
		}
		kind = 7 + uint(ext)
	}

	size := uint(ctrl & 0x1f)
	if size >= 29 {
		extra := size - 28 // 1, 2 or 3 more bytes
		raw, next, err := d.bytes(off, extra)
		if err != nil {
			return nil, 0, err
		}
		off = next
		n := uint(0)
		for _, b := range raw {
			n = n<<8 | uint(b)
		}
		switch size {
		case 29:
			size = 29 + n
		case 30:
			size = 285 + n
		default:
			size = 65821 + n
		}
	}

	switch kind {
	case typeString:
		raw, next, err := d.bytes(off, size)
		return string(raw), next, err
	case typeBytes:
		raw, next, err := d.bytes(off, size)
		if err != nil {
			return nil, 0, err
		}
		return append([]byte(nil), raw...), next, nil
	case typeDouble:
		raw, next, err := d.bytes(off, 8)
		if err != nil {
			return nil, 0, err
		}
		return math.Float64frombits(binary.BigEndian.Uint64(raw)), next, nil
	case typeFloat:
		raw, next, err := d.bytes(off, 4)
		if err != nil {
			return nil, 0, err
		}
		return float64(math.Float32frombits(binary.BigEndian.Uint32(raw))), next, nil
	case typeUint16, typeUint32, typeUint64:
		raw, next, err := d.bytes(off, size)
		if err != nil {
			return nil, 0, err
		}
		if size > 8 {
			return nil, 0, fmt.Errorf("geoip: %d-byte unsigned integer", size)
		}
		n := uint64(0)
		for _, b := range raw {
			n = n<<8 | uint64(b)
		}
		return n, next, nil
	case typeUint128:
		raw, next, err := d.bytes(off, size)
		if err != nil {
			return nil, 0, err
		}
		return append([]byte(nil), raw...), next, nil
	case typeInt32:
		raw, next, err := d.bytes(off, size)
		if err != nil {
			return nil, 0, err
		}
		if size > 4 {
			return nil, 0, fmt.Errorf("geoip: %d-byte int32", size)
		}
		n := uint32(0)
		for _, b := range raw {
			n = n<<8 | uint32(b)
		}
		return int64(int32(n)), next, nil
	case typeBool:
		return size != 0, off, nil
	case typeMap:
		m := make(map[string]any, size)
		for i := uint(0); i < size; i++ {
			key, next, err := d.decode(off, depth+1)
			if err != nil {
				return nil, 0, err
			}
			name, ok := key.(string)
			if !ok {
				return nil, 0, errors.New("geoip: map key is not a string")
			}
			value, after, err := d.decode(next, depth+1)
			if err != nil {
				return nil, 0, err
			}
			m[name] = value
			off = after
		}
		return m, off, nil
	case typeArray:
		list := make([]any, 0, min(size, 64))
		for i := uint(0); i < size; i++ {
			value, next, err := d.decode(off, depth+1)
			if err != nil {
				return nil, 0, err
			}
			list = append(list, value)
			off = next
		}
		return list, off, nil
	case typeContainer, typeEnd:
		return nil, off, nil
	}
	return nil, 0, fmt.Errorf("geoip: unknown value type %d", kind)
}

// pointer decodes a pointer's target (relative to base) and where reading
// continues after it.
func (d decoder) pointer(ctrl byte, off uint) (uint, uint, error) {
	length := uint(ctrl>>3&0x3) + 1
	raw, next, err := d.bytes(off, length)
	if err != nil {
		return 0, 0, err
	}
	high := uint(ctrl & 0x7)
	switch length {
	case 1:
		return high<<8 | uint(raw[0]), next, nil
	case 2:
		return (high<<16 | uint(raw[0])<<8 | uint(raw[1])) + 2048, next, nil
	case 3:
		return (high<<24 | uint(raw[0])<<16 | uint(raw[1])<<8 | uint(raw[2])) + 526336, next, nil
	default:
		return uint(binary.BigEndian.Uint32(raw)), next, nil
	}
}

func (d decoder) byteAt(off uint) (byte, uint, error) {
	if off >= uint(len(d.buf)) {
		return 0, 0, errTruncated
	}
	return d.buf[off], off + 1, nil
}

func (d decoder) bytes(off, n uint) ([]byte, uint, error) {
	if off > uint(len(d.buf)) || n > uint(len(d.buf))-off {
		return nil, 0, errTruncated
	}
	return d.buf[off : off+n], off + n, nil
}
