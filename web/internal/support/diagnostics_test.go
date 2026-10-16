package support

import (
	"encoding/hex"
	"testing"
)

// The same vectors as shared/tests/test_support_diagnostics.py: user_bot
// stores the hash, this side looks it up.
func TestHashDiagnosticsCodeMatchesTheBot(t *testing.T) {
	for code, want := range map[string]string{
		"ABCD-EFGH-JKLM": "3f63d25fcb898ecfd6c2e2322bfdb11f44fe17dd0dc359e70b7246224bb223e9",
		"2345 6789 zzzz": "549e28949b20b47515287b51562051f165bc799dd16dc959361dab3370bbc95d",
	} {
		got, ok := HashDiagnosticsCode(code)
		if !ok || hex.EncodeToString(got) != want {
			t.Errorf("%s: %x", code, got)
		}
	}
}

func TestNormalizeDiagnosticsCode(t *testing.T) {
	for input, want := range map[string]string{
		"ABCD-EFGH-JKLM": "ABCDEFGHJKLM",
		"abcd efgh jklm": "ABCDEFGHJKLM",
		"2345-6789-ZZZZ": "23456789ZZZZ",
		"23456789zzzz":   "23456789ZZZZ",
	} {
		if got, ok := NormalizeDiagnosticsCode(input); !ok || got != want {
			t.Errorf("%q: %q %v", input, got, ok)
		}
	}
	for _, input := range []string{"", "ABCD-EFGH", "ABCD-EFGH-JKL0", "ABCD-EFGH-JKLO", "ABCD-EFGH-JKLM-N", "ABCD_EFGH_JKLM"} {
		if _, ok := NormalizeDiagnosticsCode(input); ok {
			t.Errorf("%q accepted", input)
		}
	}
}
