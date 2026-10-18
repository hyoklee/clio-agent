# NDP website evidence

Captured on 2026-10-18 from the real local CLIO deployment. No responses were
intercepted and no product controls or data were painted into these images.

- Backend: `9544d47807fd94181739dab245daf51026c0d993` (PR #1793).
- UI: `35f3ecea0c8d16cf9eb72fa72e0e8ba7b7748bf8` (PR #647).
- Schemas: `eaa6d4cba762b6359cee1b32061f52672b04d0a5` (PR #35).
- Private local service: UI 5219, backend 8209. These are capture addresses,
  not ports required by the product or public instructions.
- Browser screenshots were taken in the actual Light appearance setting.

| Asset | Source and treatment |
| --- | --- |
| `ndp-catalog.jpg` | Real public catalog search for `WWMT.CI.LY_.40`, with only the CSV checked. Cropped from the original 1200 × 1200 browser capture: left 252, top 7, width 688, height 807. No new source was connected for this still. |
| `ndp-endpoints.jpg` | Real saved EarthScope on-demand HTTPS connection and retained response history from the UI/agent acceptance checks. Same crop origin, width 688, height 656. The service replays archived CSV data over SSE. |
| `station-chart.png` | Untouched real agent-generated PNG from analysis of the public WWMT CSV. All three panels, axes, date labels and source-unit qualifications are retained. |

The plot's input contained 857,957 data rows, 50,084,343 bytes, and SHA-256
`d4c935cf040a64c433be33be17118723bbe91abcdd00f01370e327243dd9e240`.
Dataset `2611eeb1-4efd-4ab3-badd-abacc6b64d9f`, CSV resource
`9ed2d1f4-6fd4-4720-9724-7280c2db9b4e`. Component physical units were not
established, so the figure retains “source units.”

The Endpoint check queried the existing Ares API over SSH for IU.ANMO station
metadata, and used a direct HTTPS on-demand service for three then two archived
measurements with a resume cursor. Captured bytes/hashes, non-overlapping records,
and equality to the original CSV were checked. Protected live Kafka sampling
was not qualified; an unsigned request returned HTTP 401. Catalog publisher
selection does not grant account groups or Endpoint roles.

Untouched screenshots, rejected crop attempts, reproducible `crop.mjs`, checksums
and review evidence are archived locally at
`D:/Libraries/Videos/clio_recordings/2026-10-18-ndp-website/`.
The accepted images use `raw/ndp-catalog-full.jpg` and
`raw/ndp-endpoints-full.jpg`. The later `ndp-catalog-accepted*` filenames were
rejected because a new remote search failed and displayed saved results. The
first direct clipped screenshot attempts were rejected because the browser did
not honor the requested crop origin. Keep those sources for audit; use the
derivatives above. The website uses Astro to optimize images further.

For a reshoot, open Settings → Data sources → National Data Platform → Connect,
choose the workspace, then search and select the public CSV. Capture the full
dialog after the result settles, without committing a duplicate connection.
For Endpoints & streams, select the saved on-demand connection and expand
Captured responses. Use the saved real results; do not substitute fixtures for
live data. Review the finished pages at desktop/mobile sizes in both themes.
