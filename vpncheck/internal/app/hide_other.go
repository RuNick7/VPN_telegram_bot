//go:build !windows

package app

import "os/exec"

func hide(*exec.Cmd) {}
