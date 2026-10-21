# NDP screenshot provenance correction

## Submitted image

The user's attachment `codex-clipboard-6f89efed-ffdd-47e9-8276-169c11626117.png`
is byte-for-byte identical to this earlier component-test capture:

`D:/CLIO-Develop/ndp-live-20261018/interactive-browser/ndp-source-live-catalog-fi-7c6fd-n-both-themes-and-on-mobile/ndp-light.png`

Both files have SHA-256:
`b3e891d351763a83fe15ba776878eb437be79390c0524c4fe97a54842910e510`.

This image does not show the deployed CLIO workflow. In the GACT worktree:

- `web/tests/review/ndp-source.tsx` mounts the production `NDPSourcePicker` in a
  standalone `max-w-2xl` page, outside the actual Attach dialog. Its account
  display is hard-coded to `alice` and its theme is forced by the test URL.
- `web/tests/review/ndp-source.spec.ts` intercepts the catalog, organization and
  connected-source requests. The coastal dataset, CSV/NetCDF names and Endpoint
  values are synthetic test data.
- The screenshot is a browser rendering of this controlled component fixture;
  it does not establish real NDP data access, agent behavior, or the geometry and
  scrolling of the deployed dialog. The fixture banner does not make it valid
  acceptance evidence for those claims.

The earlier `NDP-INTERACTIVE-PICKER.md` note and saved PR body identify populated
browser cases as fixtures, but also use "live filtering" and generic visual-review
wording. Those fixture checks must be read as component regressions only. Any
claim that this screenshot qualifies the live workflow is withdrawn.

The test title now says "fixture catalog filtering" and all screenshots emitted
by this spec have a `fixture-` filename prefix. Existing images are retained
unchanged for audit. No runtime UI or test assertions were changed for this label
correction.

## Direct running-application review

Opened the actual `http://127.0.0.1:5219/workspaces/ws_default/new` application,
then used **Add context → Attach → National Data Platform → Connect**. Searched
for `WWMT.CI.LY_.40` through the normal UI without route interception, injected
responses, forced theme or DOM styling changes.

The app showed its saved NDP account and one EarthScope dataset with CSV, PNG and
HTML resources. Its actual dark appearance and Attach dialog were preserved. At
the current 1280 × 720 browser size, the narrower dialog has nested scrollbars
and lower controls below the initial visible area. The standalone fixture did
not exercise that composition.

Untouched native browser capture:

`D:/Libraries/Videos/clio_recordings/2026-10-18-ndp-authenticity-review/raw/actual-clio-attach-ndp.jpg`

SHA-256: `e6760ba3218569541727fd22239445d54162f868ae2b195955ad0745f8709e3e`.

This fresh screenshot establishes the current rendered view and the returned
catalog result. No resources were selected or attached, no files were downloaded,
and no fresh agent/model turn was run. It does not claim to fix or accept the
dialog layout. The temporary review tab was closed; existing user tabs and the
running services were preserved.

## Website assets checked separately

The three NDP documentation assets match their existing archived deliverables:

| Asset | SHA-256 |
| --- | --- |
| `ndp-catalog.jpg` | `c1497002b9fcc884a2adb0ebe80ef787b41466ff78eb97f1530d774105268b05` |
| `ndp-endpoints.jpg` | `1a53f0b1bde4daabd34229be1de23f417fc291cbfd05e080da1aee139f56363d` |
| `station-chart.png` | `f6f0b757d3658e26b28dca0ac1003fc9e88e703ff9103cb83ac226a749eef713` |

The archived `raw/ndp-catalog-full.jpg` was also visually inspected: it shows the
older actual Connected data dialog with WWMT resources, rather than the coastal
fixture. This is historical screenshot provenance, not fresh verification of
the old account, network or agent acceptance claims. The documentation images
were not changed during this audit. The homepage remains outside the scope.

No commit, push, merge, release or public deployment was performed.
