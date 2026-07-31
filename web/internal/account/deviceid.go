package account

import (
	"crypto/sha256"
	"encoding/hex"
)

// DeviceID is the public handle for a device.
//
// The panel identifies devices by HWID, which is a hardware fingerprint. That
// is not something to hand to a browser and accept back in a URL, so what
// travels is a hash of it. The mapping is re-derived from a fresh listing on
// every use, which also means a stale ID resolves to nothing rather than to
// whichever device has since taken that place.
//
// 16 hex characters -- 64 bits -- is far more than enough to tell apart the
// handful of devices one subscription can hold, and it keeps the value short
// enough to read in a URL. This matches the token the bot uses for the same
// purpose in user_bot/handlers/devices.py, deliberately: the two must agree,
// or the same device would have two different identities depending on where
// the user opened it.
func DeviceID(hwid string) string {
	sum := sha256.Sum256([]byte(hwid))
	return hex.EncodeToString(sum[:])[:16]
}
