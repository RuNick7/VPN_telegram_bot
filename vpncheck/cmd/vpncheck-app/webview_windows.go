//go:build desktop && windows

package main

import "github.com/wailsapp/go-webview2/webviewloader"

// The oldest WebView2 the window works with, as Wails requires it.
const minimumWebView2 = "94.0.992.31"

// webviewInstalled reports whether Windows has a WebView2 the window can
// use. Windows 11 always does; Windows 10 usually, through Edge. Without one
// the page opens in the browser instead, rather than a download prompt.
func webviewInstalled() bool {
	installed, err := webviewloader.GetAvailableCoreWebView2BrowserVersionString("")
	if err != nil || installed == "" {
		return false
	}
	older, err := webviewloader.CompareBrowserVersions(installed, minimumWebView2)
	return err == nil && older >= 0
}
