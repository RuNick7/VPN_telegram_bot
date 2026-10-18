//go:build desktop && (windows || (darwin && cgo))

package main

import (
	"context"
	goruntime "runtime"
	"sync/atomic"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/menu"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
	"github.com/wailsapp/wails/v2/pkg/options/mac"
	"github.com/wailsapp/wails/v2/pkg/options/windows"
	wailsruntime "github.com/wailsapp/wails/v2/pkg/runtime"

	"github.com/RuNick7/vpn-check/internal/app"
)

const hasWindow = true

// runWindow shows the page in a window of the app's own, with the system's
// web view (WebKit on macOS, WebView2 on Windows), until it is closed. The
// page is asked for inside this process, with no port and no key: see
// app.WindowHandler.
func runWindow(a *app.App, smoke *smokeTest) error {
	handler := a.WindowHandler()
	if smoke != nil {
		handler = smoke.watch(handler)
	}
	var started atomic.Pointer[context.Context]
	opts := &options.App{
		Title:     appTitle,
		Width:     520,
		Height:    800,
		MinWidth:  400,
		MinHeight: 520,
		// The page's own dark ground, so the window does not flash white
		// before it is drawn.
		BackgroundColour: &options.RGBA{R: 14, G: 16, B: 20, A: 255},
		AssetServer:      &assetserver.Options{Handler: handler},
		// Right-click → «Вставить» in the link field.
		EnableDefaultContextMenu: true,
		// A second double-click brings this window up instead of starting
		// a second check beside it.
		SingleInstanceLock: &options.SingleInstanceLock{
			UniqueId: "pro.kairavpn.check",
			OnSecondInstanceLaunch: func(options.SecondInstanceData) {
				if ctx := started.Load(); ctx != nil {
					wailsruntime.WindowUnminimise(*ctx)
					wailsruntime.Show(*ctx)
				}
			},
		},
		OnStartup: func(ctx context.Context) { started.Store(&ctx) },
		OnDomReady: func(ctx context.Context) {
			if smoke != nil {
				go smoke.drive(func(js string) { wailsruntime.WindowExecJS(ctx, js) }, func() { wailsruntime.Quit(ctx) })
			}
		},
		OnShutdown: func(context.Context) { a.Stop() },
		Mac: &mac.Options{
			About: &mac.AboutInfo{Title: appTitle, Message: "Версия " + version},
		},
		Windows: &windows.Options{Theme: windows.SystemDefault},
	}
	if goruntime.GOOS == "darwin" {
		// Without an Edit menu, Cmd+V does nothing in a web view on macOS:
		// the shortcut is the menu's, not the page's.
		bar := menu.NewMenu()
		bar.Append(menu.AppMenu())
		bar.Append(menu.EditMenu())
		bar.Append(menu.WindowMenu())
		opts.Menu = bar
	}
	return wails.Run(opts)
}
