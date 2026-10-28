# Windows repair qualification

These receipts supplement the develop baseline in
`../windows-startup-2026-10-28/`. Candidate branch:
`codex/windows-startup-acceptance`, clio-agent PR #1889 and gact-tui PR #697,
both targeting develop. Product repairs were explicitly authorized after the
baseline failed. No release was tagged or published.

Each `repairN-install-cold.json` selects another empty profile and cache set;
the matching log records phase output. The first `repair-install-cold.json`
is iteration 1. OS and Defender caches were not dropped. The documents retain
unsuccessful candidates and do not select a passing result by hiding failures.

The direct-MSI and Office receipts are separate diagnostics. The pinned official
MSI was downloaded and checksum verified on this machine. Direct extraction
retained the application and all bundled fonts; office-qualification.pdf is the
real HTML-to-PDF output. These timings are not substitutes for the acceptance
matrix. The startup-graph diagnostic ran against an already installed environment.

The focused test logs cover the changed installer, native extraction validation,
protection handling, worker ownership, public infrastructure imports, and startup
bytecode validity. They do not claim develop CI or release-wide tests pass.
