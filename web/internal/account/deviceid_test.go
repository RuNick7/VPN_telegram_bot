package account

import "testing"

func TestDeviceIDIsStable(t *testing.T) {
	// The ID is re-derived on every request, so an unstable one would make
	// every device look like it had vanished between page loads.
	if DeviceID("HW-1") != DeviceID("HW-1") {
		t.Error("same HWID produced different IDs")
	}
}

func TestDifferentDevicesGetDifferentIDs(t *testing.T) {
	if DeviceID("HW-1") == DeviceID("HW-2") {
		t.Error("two devices share an ID")
	}
}

func TestTheHardwareFingerprintIsNotExposed(t *testing.T) {
	// An HWID identifies a physical machine. It is not ours to publish into a
	// URL, and it must not be recoverable from what we do publish.
	const hwid = "AA-BB-CC-DD-EE-FF"
	if id := DeviceID(hwid); id == hwid || len(id) != 16 {
		t.Errorf("DeviceID(%q) = %q", hwid, id)
	}
}

func TestIDMatchesTheBotsToken(t *testing.T) {
	// user_bot/handlers/devices.py derives the same value. If the two ever
	// disagreed, one device would have two identities depending on whether
	// the user opened it in the bot or on the site.
	//
	// These are what `device_token()` returns in Python, pinned literally so
	// a change to either side breaks here rather than in production.
	want := map[string]string{
		"HW-IPHONE":         "e3119c8b04da1ecd",
		"HW-1":              "a8514fa5a49ec82c",
		"AA-BB-CC-DD-EE-FF": "4ede89a251930543",
	}
	for hwid, expected := range want {
		if got := DeviceID(hwid); got != expected {
			t.Errorf("DeviceID(%q) = %q, want %q", hwid, got, expected)
		}
	}
}
