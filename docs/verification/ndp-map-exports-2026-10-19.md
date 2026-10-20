# Native transcript map worker repair

The saved map data was present, but a portable/restricted-origin document could
show its controls and legend with an empty canvas. An isolated native-viewer
fixture using the retained 2,340 California station rows reproduced the failure
at a sandboxed opaque origin; the same fixture rendered at a normal HTTP origin.

The archive embeds a classic IIFE worker. MapLibre 6 infers worker format from
the URL and, for the old blob URL at a restricted origin, inserts a module-import
wrapper. Its additional import cannot run under the archive CSP. Declaring the
worker's classic format via a `.cjs` fragment preserves the blob identity and
removes that extra import. Neither CSP nor external network permissions changed.
The frontend implementation and regression are in gact-tui PR 660.

Four browser cases pass using the production worker build and actual MapLibre
rendered layers: points and polygon, each under normal and opaque origins. The
labelled synthetic test inputs are not scientific evidence. The real retained
station-map fixture also draws after the fix. Twenty-six focused map/archive
unit tests, frontend typecheck, touched-file lint and the offline build pass.

Native exports for Alta, Tahoe, Konza and the withdrawn Ares conversation were
regenerated. Recorded messages, tool records, loaded skill bodies, semantic
history and visual snapshots compare exactly with the retained originals.
Only viewer packaging and export metadata changed. Old exports are retained.
Direct file-protocol navigation was not available in the automation browser;
the restricted-origin regression and its real rendered geometry are the stated
browser evidence, not a claim of testing every browser/file association.

The public index pins versioned `*-session-maps-v2.html` downloads, so earlier
published bytes and their checksums remain recoverable. Public Tahoe also has a
regression asserting rendered geometry in a sandboxed native-conversation frame.
The Ares conversation remains withdrawn and its refreshed HTML is diagnostic
only. This renderer fix does not establish stream-science acceptance.

Exact export hashes, original hashes, scripts, browser logs and untouched
screenshots are retained in
`D:/CLIO-Develop/ndp-transcript-maps-20261019/`.
