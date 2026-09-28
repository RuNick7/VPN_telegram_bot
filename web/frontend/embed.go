// Package frontend carries the customer website's static files into the
// binary.
//
// Embedding rather than reading from disk is what makes the deployment a
// single artefact: there is no directory the server can be pointed at by
// mistake, and no way for the files on a running host to drift from the code
// that expects them.
//
// The patterns are explicit so this source file is not itself embedded and
// served. A directory missing from the list is a silent 404 at run time and
// nothing at build time, so `TestEveryRouteOfTheRealSiteRenders` in
// cmd/server is what actually holds this line honest -- adding `docs/` was
// forgotten once and the agreements 404'd on a deployed site.
package frontend

import "embed"

//go:embed *.html app assets docs
var Files embed.FS
