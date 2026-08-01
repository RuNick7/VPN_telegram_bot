// Package frontend carries the customer website's static files into the
// binary.
//
// Embedding rather than reading from disk is what makes the deployment a
// single artefact: there is no directory the server can be pointed at by
// mistake, and no way for the files on a running host to drift from the code
// that expects them.
//
// The patterns are explicit so this source file is not itself embedded and
// served.
package frontend

import "embed"

//go:embed *.html app assets
var Files embed.FS
