package app

import (
	"bytes"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// desktop is what the app asks of the computer it runs on. Each is a
// command the system already has, so there is nothing to link against and
// one build works on every version of it.
type desktop interface {
	// CopyFile puts the file itself on the clipboard, the way copying it in
	// Finder or Explorer does, so it can be pasted into a Telegram chat.
	CopyFile(path string) error
	// ReadText is the clipboard's text.
	ReadText() (string, error)
	// Reveal shows the file in Finder or Explorer.
	Reveal(path string) error
	// Open opens a page in the browser.
	Open(url string) error
}

type system struct{}

var errNoClipboard = errors.New("нет программы для работы с буфером обмена (нужна wl-clipboard или xclip)")

func (system) CopyFile(path string) error {
	switch runtime.GOOS {
	case "darwin":
		// What Finder's Copy puts there: the file's URL, which Telegram and
		// Mail take as an attachment.
		script := `function run(argv) {
			ObjC.import('AppKit');
			const board = $.NSPasteboard.generalPasteboard;
			board.clearContents;
			board.writeObjects($.NSArray.arrayWithObject($.NSURL.fileURLWithPath(argv[0])));
		}`
		return quiet(exec.Command("osascript", "-l", "JavaScript", "-e", script, path))
	case "windows":
		// Windows PowerShell 5, which every Windows 10 and 11 has, puts a
		// file-drop list there; the path goes in the environment so nothing
		// in it is ever read as a command.
		cmd := exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
			"Set-Clipboard -LiteralPath $env:VPNCHECK_FILE")
		cmd.Env = append(os.Environ(), "VPNCHECK_FILE="+path)
		return quiet(cmd)
	}
	list := "file://" + filepath.ToSlash(path) + "\n"
	for _, try := range [][]string{
		{"wl-copy", "--type", "text/uri-list"},
		{"xclip", "-selection", "clipboard", "-t", "text/uri-list", "-i"},
	} {
		if _, err := exec.LookPath(try[0]); err != nil {
			continue
		}
		cmd := exec.Command(try[0], try[1:]...)
		cmd.Stdin = strings.NewReader(list)
		return quiet(cmd)
	}
	return errNoClipboard
}

func (system) ReadText() (string, error) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "darwin":
		cmd = exec.Command("pbpaste")
	case "windows":
		cmd = exec.Command("powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
			"[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-Clipboard -Raw")
	default:
		for _, try := range [][]string{{"wl-paste", "--no-newline"}, {"xclip", "-selection", "clipboard", "-o"}} {
			if _, err := exec.LookPath(try[0]); err == nil {
				cmd = exec.Command(try[0], try[1:]...)
				break
			}
		}
		if cmd == nil {
			return "", errNoClipboard
		}
	}
	hide(cmd)
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return "", err
	}
	// A link is short; whatever else is on the clipboard is not ours to read.
	text := out.String()
	if len(text) > 4096 {
		text = text[:4096]
	}
	return text, nil
}

func (system) Reveal(path string) error {
	switch runtime.GOOS {
	case "darwin":
		return quiet(exec.Command("open", "-R", path))
	case "windows":
		// Explorer reports failure even when it opens the window.
		cmd := exec.Command("explorer.exe", "/select,"+path)
		hide(cmd)
		_ = cmd.Run()
		return nil
	}
	return quiet(exec.Command("xdg-open", filepath.Dir(path)))
}

func (system) Open(url string) error { return OpenBrowser(url) }

// OpenBrowser opens a page in the default browser.
func OpenBrowser(url string) error {
	switch runtime.GOOS {
	case "darwin":
		return quiet(exec.Command("open", url))
	case "windows":
		return quiet(exec.Command("rundll32", "url.dll,FileProtocolHandler", url))
	}
	return quiet(exec.Command("xdg-open", url))
}

// quiet runs a command with no window of its own and returns its complaint
// as the error.
func quiet(cmd *exec.Cmd) error {
	hide(cmd)
	var stderr bytes.Buffer
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		if msg := strings.TrimSpace(stderr.String()); msg != "" {
			return fmt.Errorf("%s: %s", filepath.Base(cmd.Path), lastLine(msg))
		}
		return fmt.Errorf("%s: %w", filepath.Base(cmd.Path), err)
	}
	return nil
}

func lastLine(s string) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	return strings.TrimSpace(lines[len(lines)-1])
}
