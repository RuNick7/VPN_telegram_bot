//go:build !(desktop && (windows || (darwin && cgo)))

package main

import (
	"errors"

	"github.com/RuNick7/vpn-check/internal/app"
)

// Built without the window (Linux, or without -tags desktop): the page
// opens in the browser.
const hasWindow = false

func runWindow(*app.App, *smokeTest) error { return errors.New("no window in this build") }

func webviewInstalled() bool { return false }
