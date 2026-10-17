package app

import (
	"archive/zip"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
	"strings"
)

// How many runs stay on disk. The newest is what the buttons act on; a few
// before it cost little and outlive a slip of the finger.
const keepRuns = 10

// archive packs a run's folder into one zip next to it, named for the
// moment the run started, which is the name support sees in the chat.
func archive(dir string) (string, error) {
	path := filepath.Join(filepath.Dir(dir), "vpncheck-"+filepath.Base(dir)+".zip")
	if _, err := os.Stat(path); err == nil {
		return path, nil
	}
	tmp := path + ".part"
	out, err := os.Create(tmp)
	if err != nil {
		return "", err
	}
	zw := zip.NewWriter(out)
	walkErr := filepath.WalkDir(dir, func(file string, entry os.DirEntry, err error) error {
		if err != nil || entry.IsDir() {
			return err
		}
		rel, err := filepath.Rel(dir, file)
		if err != nil {
			return err
		}
		w, err := zw.Create(filepath.ToSlash(rel))
		if err != nil {
			return err
		}
		in, err := os.Open(file)
		if err != nil {
			return err
		}
		defer in.Close()
		_, err = io.Copy(w, in)
		return err
	})
	closeErr := zw.Close()
	fileErr := out.Close()
	for _, err := range []error{walkErr, closeErr, fileErr} {
		if err != nil {
			os.Remove(tmp)
			return "", err
		}
	}
	return path, os.Rename(tmp, path)
}

// saveCopy copies file into dir under its own name, adding " (2)" and so on
// rather than overwriting a report saved before.
func saveCopy(file, dir string) (string, error) {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return "", err
	}
	ext := filepath.Ext(file)
	stem := strings.TrimSuffix(filepath.Base(file), ext)
	for n := 1; ; n++ {
		name := stem + ext
		if n > 1 {
			name = fmt.Sprintf("%s (%d)%s", stem, n, ext)
		}
		target := filepath.Join(dir, name)
		out, err := os.OpenFile(target, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o644)
		if os.IsExist(err) {
			continue
		}
		if err != nil {
			return "", err
		}
		in, err := os.Open(file)
		if err != nil {
			out.Close()
			return "", err
		}
		_, err = io.Copy(out, in)
		in.Close()
		if closeErr := out.Close(); err == nil {
			err = closeErr
		}
		if err != nil {
			os.Remove(target)
			return "", err
		}
		return target, nil
	}
}

// pruneRuns keeps the newest keep runs under root, each a folder named by
// its start time and maybe a zip of it, and removes the rest.
func pruneRuns(root string, keep int) {
	entries, err := os.ReadDir(root)
	if err != nil {
		return
	}
	var runs []string
	for _, entry := range entries {
		if entry.IsDir() {
			runs = append(runs, entry.Name())
		}
	}
	slices.Sort(runs)
	for len(runs) > keep {
		os.RemoveAll(filepath.Join(root, runs[0]))
		os.Remove(filepath.Join(root, "vpncheck-"+runs[0]+".zip"))
		runs = runs[1:]
	}
}

// DownloadsDir is where a browser would put a file: ~/Downloads, which
// macOS and Windows both have whatever their language.
func DownloadsDir() string {
	home, err := os.UserHomeDir()
	if err != nil {
		return "."
	}
	if info, err := os.Stat(filepath.Join(home, "Downloads")); err == nil && info.IsDir() {
		return filepath.Join(home, "Downloads")
	}
	return home
}

func readLink(path string) string {
	if path == "" {
		return ""
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

// The link is a secret: whoever has it has the customer's VPN. It is kept
// only in the user's own config directory, readable by them alone, the way
// the VPN app itself keeps it.
func writeLink(path, link string) {
	if path == "" {
		return
	}
	if link == "" {
		os.Remove(path)
		return
	}
	if os.MkdirAll(filepath.Dir(path), 0o700) == nil {
		_ = os.WriteFile(path, []byte(link+"\n"), 0o600)
	}
}
