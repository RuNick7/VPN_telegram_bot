package panel

import (
	"encoding/json"
	"testing"
)

// Two generations of the panel identify users differently: older ones return a
// `uuid`, newer ones dropped it for a numeric `id`. Getting this wrong is not
// a cosmetic bug -- the client reported every existing account as missing,
// tried to create it again, and was told the name was taken, on every single
// request. These pin both shapes.

func TestRefPrefersUUIDAndFallsBackToID(t *testing.T) {
	cases := []struct {
		name string
		body string
		want string
	}{
		{
			name: "older panel: uuid",
			body: `{"uuid":"c2400d02-06a0-4b21-a310-d1a888a088bb","username":"u-abc"}`,
			want: "c2400d02-06a0-4b21-a310-d1a888a088bb",
		},
		{
			name: "newer panel: numeric id, no uuid at all",
			body: `{"id":2,"username":"u-abc","shortUuid":"SayZcYcdx7zRHfxe"}`,
			want: "2",
		},
		{
			// A panel serving both must not have the id win: the uuid is the
			// stabler handle and is what older stored rows already contain.
			name: "both present",
			body: `{"uuid":"c2400d02-06a0-4b21-a310-d1a888a088bb","id":2}`,
			want: "c2400d02-06a0-4b21-a310-d1a888a088bb",
		},
		{
			name: "neither",
			body: `{"username":"u-abc"}`,
			want: "",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var user User
			if err := json.Unmarshal([]byte(tc.body), &user); err != nil {
				t.Fatalf("decode: %v", err)
			}
			if got := user.Ref(); got != tc.want {
				t.Errorf("Ref() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestANilUserHasNoRef(t *testing.T) {
	var user *User
	if got := user.Ref(); got != "" {
		t.Errorf("Ref() = %q on a nil user", got)
	}
}

func TestIdentifyNamesTheAccountTheWayEachPanelExpects(t *testing.T) {
	// `PATCH /users` on the newer panel answers "At least one of username, id
	// must be provided" and wants id as a *number*; the older one wants a uuid
	// string. Sending the wrong key, or the right key with the wrong JSON
	// type, is a 400 either way.
	numeric := identify("2")
	if id, ok := numeric["id"].(int64); !ok || id != 2 {
		t.Errorf("identify(\"2\") = %#v, want id as a number", numeric)
	}
	if _, present := numeric["uuid"]; present {
		t.Error("a numeric ref must not also be sent as uuid")
	}

	uuid := identify("c2400d02-06a0-4b21-a310-d1a888a088bb")
	if got, ok := uuid["uuid"].(string); !ok || got != "c2400d02-06a0-4b21-a310-d1a888a088bb" {
		t.Errorf("identify(uuid) = %#v", uuid)
	}
	if _, present := uuid["id"]; present {
		t.Error("a uuid ref must not also be sent as id")
	}
}

func TestNumericRefDoesNotMistakeAUUIDForAnID(t *testing.T) {
	// This is the whole basis for storing one string and later working out
	// which panel produced it, so it has to be exact.
	if _, ok := numericRef("c2400d02-06a0-4b21-a310-d1a888a088bb"); ok {
		t.Error("a uuid was read as a numeric id")
	}
	if _, ok := numericRef(""); ok {
		t.Error("an empty ref was read as a numeric id")
	}
	if _, ok := numericRef("2f"); ok {
		t.Error("a hex-looking string was read as a numeric id")
	}
	if n, ok := numericRef("2"); !ok || n != 2 {
		t.Errorf("numericRef(\"2\") = %d, %v", n, ok)
	}
}

func TestIDDecodesWhetherItArrivesAsANumberOrAString(t *testing.T) {
	// json.Number tolerates both, which keeps a panel that quotes its ids from
	// failing the whole decode and taking every endpoint down with it.
	for _, body := range []string{`{"id":2}`, `{"id":"2"}`} {
		var user User
		if err := json.Unmarshal([]byte(body), &user); err != nil {
			t.Errorf("decode %s: %v", body, err)
			continue
		}
		if got := user.Ref(); got != "2" {
			t.Errorf("decode %s: Ref() = %q, want 2", body, got)
		}
	}
}
