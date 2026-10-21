# Source connection receipts and direct file opening

The reported session was `sess_3511cbaf2a25` in workspace `ws_5864c27f6197`.
Its two NDP connection calls returned real accepted Indexing task handles. Both
source manifests subsequently listed two resources, and the agent read both
CSVs and both readmes. Those calls did not report an unavailable storage service.

## Cause and change

`connected_data_connect` reused the inventory presenter. That presenter expected
`status: available`; a valid task acceptance instead has `status: running`.
Consequently it emitted “Connected data is unavailable” for successful task
submission. Downloads had the corresponding “0 task outcomes” problem because
their presenter only understood collected task results.

The native presenters now distinguish task acceptance, terminal outcomes, an
already linked source and a sign-in requirement. Accepted work is labeled
“Indexing requested” or “Download requested” and retains snapshot semantics;
acceptance does not claim that indexing or download has completed.

The UI also repairs those specific old receipts from their recorded accepted
task return. It handles mapping, structured-content, JSON string and single-text
part representations. It leaves raw observations and unknown/failed calls intact.

Compact file/resource/artifact result rows now offer an explicit Open action
beside technical details. It uses the existing owner-scoped workbench navigation,
without a nested button or requiring the result disclosure to be expanded.
Unavailable references do not acquire a fake Open action.

## Actual browser review

The original stored CLIO conversation was opened in the production preview at
`http://127.0.0.1:5219`, rather than reconstructed in a fixture. Its two connection
receipts now show “Indexing requested.” Both download receipts show “Download
requested.” Direct Open actions were exercised for all four original resources:

- `1-20250409_CLN_2023_2024_complete_Wasserstein.csv`: table preview, 426 rows.
- `2-STEENBURGH_readme20250408.txt`: original readme text.
- `1-CLN_1999_2023_complete_v2.csv`: table preview, explicitly capped at the first
  1,000 parsed rows by the existing viewer.
- `2-steenburgh_readme20230915.txt`: original readme text.

This is live UI interaction with an existing real agent run, not a new model
trial. The historical run also contains a later genuine revision-mismatch error;
that recorded error remains an error. No revision check or permission was relaxed.

The backend was restarted only after the session inventory showed no active
conversations, using the same private home, account store, Core namespace and
workspace state. The UI remains on port 5219; the backend remains on port 8209.

Local evidence is in `D:/CLIO-Develop/ndp-unavailable-20261018/`, including
`actual-open-source.csv.jpg`, test/type logs and the running backend log.

## Checks

- 31 unique Python cases passed: 23 across submission presentation, source
  connection runtime and source/account setup; 16 across connection runtime and
  shared task wait presentation, with 8 runtime cases overlapping.
- 56 UI cases cover legacy receipts, direct opening, tool results, observability
  and transcript entries. Includes keyboard activation and missing references.
- Focused Ruff, Pyright, oxlint, TypeScript and diff checks passed.
- Existing deprecation, development/async-act and nanobind exit warnings remain
  visible in the logs. No test was skipped or accepted as failing.

This review does not assert protected NDP stream acceptance or scientific
correctness of the earlier analysis. Nothing was merged or released.
