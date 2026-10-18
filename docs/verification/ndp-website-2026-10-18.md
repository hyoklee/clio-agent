# NDP website coverage

The NDP campaign includes its public website documentation in the same backend
PR. Publication still follows the normal `develop` → `main` release/deployment
path; these edits do not deploy the website or release an installer themselves.

## Reader entry points

- `/docs/files/ndp/`: catalog search, publisher filtering, resource selection,
  normal Download/Link review, private sign-in, existing URL/SSH Endpoints,
  operation review, bounded capture, cursor resume and producer ownership.
- `/docs/examples/ndp-earthscope/`: repeatable default-agent request, actual
  downloaded CSV findings and PNG, plus finite three-record/two-record replay.
- Bring your data sidebar, Files guide navigation, source table, copies guide,
  worked examples, version availability and data/network guide link into NDP.
- `/media/guides.json` includes tutorial captures with their source directories,
  captions and development availability. Existing capture references keep their
  previous resolution behavior.

The homepage is outside the NDP documentation scope. The NDP homepage section
and its unused component have been removed locally at the user's request; the
homepage source matches the revision before the NDP addition. The official mark,
catalog screenshots, guide, example and documentation navigation remain.
This correction has not been committed or pushed; merges and releases remain frozen.

## Evidence and boundaries

The screenshots come from the actual local deployment, in Light appearance.
No network interception or fixture responses were used. The station chart is
the original agent-produced output. Source metadata, crop coordinates, backend
and UI revisions, rejected takes and archive details are documented in
`site/src/assets/tutorials/ndp/README.md`.

Dataset access and Endpoint operation access are described separately. Catalog
publisher selection does not grant an account group. The test identity service
and production client registration requirement are explicit. The example labels
archived CSV replay correctly and does not claim qualified protected live Kafka
consumption. All NDP reader entry points identify development availability.

## Original verification before the homepage correction

- `pnpm test`: 33 tests passed.
- `pnpm check`: 0 errors, 0 warnings (six pre-existing informational hints).
- `pnpm build`: 94 pages, all internal links valid.
- `pnpm test:browser`: 37 tests passed, no skips, including the four new NDP
  cases at 390/1440 pixels in Light/Dark. Image expansion, focus return, navigation,
  chart loading, logo visibility, media references and horizontal fit are checked.
- A final homepage typography/alignment adjustment uses existing website tokens;
  the production/link build and four NDP browser cases are rerun after that edit.
- `npm test` in `site/video`: five tests passed, no skips.
- Manual browser review covers the built homepage and guide; actual screenshots
  and plot are separately inspected for content, labels and clipping.

The initial local checkout lacked generated gallery files. Reusing older staged
files exposed a carousel failure; the accepted run builds from the exact Pages
workflow UI pin, `bbc1411d1c459b10a994c9afa79887cb79abfb47`, in an isolated
checkout, prepares the docs entry and stages it with the repository scripts.
No existing test was weakened or skipped. The NDP browser cases now start at the
guide and check the official mark there, rather than requiring a homepage section.

During this work, hosted backend CI identified the new Endpoint validator in
the schema-library guard. The production validator now explicitly uses a registry
without network retrieval. The guard additionally proves refusal for both remote
`$ref` and `$dynamicRef`, with the network socket layer armed to fail.
Thirty schema/Endpoint workflow tests, Ruff and focused Mypy pass. The installed
Core binding still prints its known nanobind reference-leak diagnostics at test
process exit; those messages are retained in the local log.

Raw screenshots, verified deliverable copies, crop script, checksums and review
evidence are archived at
`D:/Libraries/Videos/clio_recordings/2026-10-18-ndp-website/`. Detailed build and
test logs are retained under `D:/CLIO-Develop/ndp-live-20261018/ndp-site-*.log`.
Hosted checks on the pushed revision are distinct from these local results.

## Homepage correction verification

- The homepage MDX blob is `e0c5005d631e0463482b2566f2c02865f2253135`,
  identical to `214a5277^:site/src/content/docs/index.mdx`.
- Removed the homepage-only `overview/Ndp.astro`; the shared documentation logo
  component, guide, example and assets remain.
- `pnpm test`: 33 passed, no skips.
- `pnpm check`: 0 errors, 0 warnings, six existing informational hints.
- `pnpm build`: 94 pages built; all internal links valid. The build reports the
  existing Vite module-directive warnings.
- `pnpm test:browser e2e/ndp.spec.ts e2e/navigation.spec.ts`: 11 passed, no skips,
  covering navigation and the NDP guide/example at 390/1440 pixels in Light/Dark.
  The initial run exposed a stale two-image expectation: the earlier Endpoint
  documentation correction had already removed the obsolete API screenshot.
  The corrected check explicitly verifies the retained catalog image and the
  EarthScope chart, including both media URLs.
- Manual browser review at `http://127.0.0.1:4391/` confirms the evidence section
  leads directly into the existing workflow section. The NDP guide still loads
  with its official logo and documentation navigation. Screenshots are retained
  in `D:/CLIO-Develop/ndp-homepage-removal-20261018/`.

No commit, push, merge, release or public deployment was performed for this correction.
