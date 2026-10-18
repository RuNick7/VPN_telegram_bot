package app

import (
	"os/exec"
	"syscall"
)

// hide keeps a helper command from flashing a console window over the app.
func hide(cmd *exec.Cmd) {
	const createNoWindow = 0x08000000
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: createNoWindow}
}
