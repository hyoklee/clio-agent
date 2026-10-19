# Approved source reads through the shell

## Incident and cause

The actual CLIO session `sess_68677a4cffe8` could read the short Alta-Collins
2023–24 CSV with connected-data tools but could not analyze the historical CSV.
Its shell call was a read-only PowerShell directory listing:

```powershell
Get-ChildItem -LiteralPath '<approved historical snapshot>'
```

The call declared both downloaded snapshots in `access_paths`. In
`gact/folder_access.py`, `requested_folders()` classified every tool except
`fs_read_file` as a write. Connected-source policy therefore rejected the
declared paths before the shell or OS sandbox executed. This was an application
gate bug, not an OS refusal and not an upstream NDP failure.

The original receipt is retained in
`D:/CLIO-Develop/ndp-live-20261018/home/state/traces/semantic_traces/sess_68677a4cffe8.semantic.jsonl`.

## Change

- Recognize approved workspace source copies in the file policy, folder gate
  and shell working-directory validation using the same durable source ledger.
- Treat shell declarations as paths needing access, rather than proof of write
  intent. Approved copies need no additional writable folder grant.
- Preserve credential and symlink checks, explicit edit-tool write rejection,
  unapproved-folder checks and the requirement for an enforcing child sandbox.
- Keep source write exclusions in the existing OS profile. Save analysis outputs
  in the workspace. No command-text classifier or read-only command allowlist is
  involved.

## Actual filesystem acceptance

Evidence: `D:/CLIO-Develop/source-shell-access-20261018/`.
The standalone harnesses call the production FastMCP shell server and real
Windows Codex MXC sandbox. No fake shell, mocked fence or simulated result is
used for these checks.

`qualify_fence.py` creates a disposable local connected source, downloads it
through `StorageService` and `materialize`, and removes ordinary read-only file
attributes from the disposable text inputs. It then runs a real Python child
through the shell, once with a workspace working directory and once with the
approved snapshot as working directory.

Both runs pass all 12 witnesses:

| Operation | Observed result |
| --- | --- |
| Read and calculate over the source CSV | Allowed |
| Write a derived JSON result in the workspace | Allowed |
| Overwrite an existing source file | Permission denied |
| Append to a source file | Permission denied |
| Create a new file inside the source | Permission denied |
| Rename a source file | Permission denied |
| Delete a source file | Permission denied |
| Move a source file into the workspace | Permission denied |
| Rename a directory inside the source | Permission denied |
| Change source file metadata | Permission denied |
| Read a private credential fixture | Permission denied |
| Write to a source from a descendant Python process | Permission denied |

Source filenames and SHA-256 hashes remain unchanged. No writable root grants
are created. Results and exact commands are in `fence-results.json`.

`read_actual_ndp.py` repeats the refused listing against the session's actual
historical snapshot and reads both complete CSVs through the production fenced
shell. Both commands exit zero with empty stderr:

| Actual NDP download | Nonempty data rows |
| --- | ---: |
| `1-CLN_1999_2023_complete_v2.csv` | 9,940 |
| `1-20250409_CLN_2023_2024_complete_Wasserstein.csv` | 426 |

Both headers are `Time (LST)`, `12 hr Snow (in.)`, `12 hr LPE (in.)`.
All actual downloaded file hashes remain unchanged. Full receipts are in
`actual-ndp-results.json`. The original scientific files are never used for
mutation attempts.

These are direct tool/runtime acceptance checks. They establish filesystem
access and protection, not completion of a fresh model-authored scientific
comparison or validation on other operating systems.

## Regression checks and running preview

106 tests pass across source shell access, folder approvals, shell execution,
file policy, storage-ledger access and Codex profile/detection. Ruff and Pyright
pass. Two existing PATH-fallback detection tests needed their bundled-runtime
dependencies injected explicitly; they retain the same PATH-order assertions.
Deprecation and existing nanobind shutdown warnings remain in the test log.

The preview backend was restarted only after verifying all 23 conversations
were idle and all 31 recorded runs were terminal. The existing home, NDP account
store, workspaces and sessions were retained. The UI at
`http://127.0.0.1:5219/` returns HTTP 200; protected execution still reports
`ready` / `fence_active`. No merge or release was performed.

An initial failed test run left the private runtime directory
`D:/Libraries/Documents/projects/.clio-ndp-source.pytest-runtime/run-38816-cdb5c62ef736`.
The new SQLite fixture now closes its connection explicitly, and the final run
does not report a cleanup failure. Automatic approval review rejected a scoped
PowerShell removal of that earlier directory with `blocked by policy` and no
further reason; the earlier directory has therefore been left in place.
