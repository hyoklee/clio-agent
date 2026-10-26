# Morning report: Polaris readiness (2026-10-26)

Goal: [GOAL.md](GOAL.md). Polaris entry point: [HANDOFF.md](HANDOFF.md). Branch
`claude/epic-hopper-6s2vhn` in iowarp/clio-agent, iowarp/gact-tui, iowarp/clio-schemas
(unchanged) and iowarp/clio-agent-marketplace. clio-agent pins both submodules to the branch.

## A. Bogdan's attention semantics: done, verified against his own code

Spec: spotter-ai-genesis/experiments `bench/opal/analytics` @ `ebe17be`
(`attn_analytics.py`, `render_heatmap.py`).

| His rule | CLIO now |
|---|---|
| `score[j] = Σ_i 0.5^i · val_all_max[step_i][j]`, unnormalized, item's first step weighted most | Default profile `attn-analytics` (`gact/attention/profiles.py`). The old uniform-mean and decayed-max presets stay in the heat-profile editor; "SPOTTER" is the new preset. |
| One vector per answer item | `POST /v1/sessions/{sid}/messages/{mid}/attention/items`: items are explicit spans, or one selection split at a delimiter (default `;`). Each item is reduced on its own decode steps, never unioned. |
| Whole prompt, per line, max over the line's tokens, each column scaled to its own max, ramp ` .:-=+*#%@` | Same payload: `lines[].levels`. UI: **Prompt heat map** in the attention banner (one numbered column per item, section labels, "Only lines with heat", Download CSV). |
| CSV `chain_id … prompt_token_ids, scores` | `POST …/attention/items/export` writes his exact columns, so `render_heatmap.py` reads it as is. |
| Unretained positions score 0; connector `-1` slots dropped | `-1` (`NO_ENTRY`) slots are now dropped. Before, CLIO refused the whole capture as malformed. |

**Parity proof** (`tests/test_gact/test_attention/test_items.py`, on the real capture fixture from job
3237185): his `aggregate()` and `render()`, copied verbatim into
`tests/test_gact/test_attention/spotter_reference.py`, produce the same per-token scores (exact at the
CSV's 6 digits) and the same ramp cell on every line. One subtlety: line levels are computed from the
6-digit published scores, because his renderer reads the CSV, and saturated maxima sit exactly on a
rounding tie (`9 · 1.0 / 2.0 = 4.5`).

Screenshots of the heat map over the recorded capture:
`evidence/attention-ui/heat-4-heatmap-split-period.png`, `heat2-5-heatmap-all-lines.png`.

**Known difference:** if the tokenizer merges a separator into an item's token (`373;`), CLIO's item
includes that token, while his script drops it. Items are character spans in CLIO.

### Questions only Bogdan can answer

1. **Items in free prose.** CLIO answers are not `ANSWER: a; b`. Today an item is the person's
   selection, split at a delimiter they choose. Is that right, or should items come from structure
   (list items, table cells, sentences)?
2. **Multi-call answers.** An answer built over several model calls (tool steps between them): is each
   call's output its own set of items?
3. **Reasoning tokens.** Should `<think>` steps count? Today a selection inside the reasoning maps to
   the reasoning's own steps.
4. **CLIO's additions.** CLIO still shows a "Sources" breakdown by uniform mean mass plus a "spread
   thin" residual, and its drill-down ranks by the mean because `val_all_max` saturates at 1.0. Keep
   them as secondary, or drop them?
5. **Below the cut.** Should a score of 0 below the top-10% cut be shown as blank (his ramp) or marked
   "not captured"?

## B. OPAL driver: done

`python -m scripts.qualification.opal_chain_run`:

- prepares any chain of `opal_chains.csv` (the A/B injection pair stays specific to
  `exp32-chain-0020-hard`);
- runs it through a fresh SPOTTER session (`beta3_opal_run`);
- exports every round's `ANSWER:` items as his CSV (`attention-<cond>.csv`);
- scores the answers locally (`score-<cond>.json`). The correct answers never leave the operator
  directory.

No teacher forcing. Tests: `tests/test_scripts/test_opal_chain_run.py`.

## C. Polaris kit: written, statically checked, not run on a GPU

See [HANDOFF.md](HANDOFF.md). CLIO itself deploys Flowcept (native; Apptainer is the labelled
fallback) and vLLM `native-cuda-attention` serving Granite 4.2-30B at **tensor parallel 4** (the whole
node, about 128k context). It then runs one attention smoke turn before OPAL.

- Checks: `bash -n`, shellcheck, `py_compile`, `DRY_RUN=1` of every step, and kit.py's control flow
  against a stand-in REST server.
- Routes are verified from the code, with file:line in HANDOFF.

## D. Live check in the cloud session

(filled in below)

## Open risks for Polaris

1. **Attention capture under tensor parallelism on CUDA has never run.** The connector pin `95ab2ac`
   gathers per-rank maxima and rank 0 writes the file. The smoke turn checks this first, and the
   capture metadata must show the global head counts (32 query / 8 KV heads).
2. **Connector build fix.** The pinned connector does not build without a one-line fix. The kit builds a
   patched wheel locally. Nothing was pushed to spotter-ai-genesis.
3. **ALCF details not checkable from here:** queue names (`capacity`), `/local/scratch`, module names
   for Apptainer, and the driver version (preflight flags a driver older than 570).
