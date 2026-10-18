//go:build desktop && darwin && cgo

package main

// WebKit is part of macOS.
func webviewInstalled() bool { return true }
