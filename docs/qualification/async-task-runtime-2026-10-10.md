# Integrated asynchronous task runtime qualification

The consolidated current review is [Agent-facing Tasks: use cases and
acceptance](agent-facing-tasks-use-cases.md). The integration and runtime
preflight below are historical snapshots, not final-source acceptance.

The task implementation is integrated in core develop `4314bbb0`, with GACT
`e7d7de52` and marketplace `db6d6b7`. This does not establish full live acceptance.
Earlier model receipts retain their original source and runtime identities.

The isolated Linux qualification environment uses Python 3.14.6 and Core 2.3.1.
Its host has glibc 2.31. The integrated lock's `orjson==3.11.3` Python 3.14 Linux
wheel requires glibc 2.34; locked wheel installation therefore failed before any
model or task was submitted. Updating only the locked orjson package to 3.13.0
allows the existing environment to install the exact lock, including the Claude
SDK extra and Codex CLI 0.162.1. No runtime limits or task semantics changed.

Preflight commands, the original and updated locks, package inventories and
installation logs are retained under `mcp-agent-tasks/integrated-4314-runtime-preflight-1`
in the release-recovery evidence directory. Production installation and host
authentication are outside this qualification run.

Remaining acceptance includes final-source actual-model mixed controls,
completion delivery and lifecycle races. Unit tests, an installed environment,
and CI are supporting evidence; none replaces these live gates. Historical
failures and unavailable or prohibited routes remain open until separately
resolved.

One retained Haiku mixed-task failure has a narrower diagnosis. Its short wait
returned in 0.255 seconds and the canonical result reached the SDK. The following
public response streamed 7,106 HTML line-break tags and no meaningful text. That
output kept the inter-token silence watchdog alive; it does not show a blocked
task wait. Other retained response stalls have different evidence and remain open.

For tool-capable Claude calls, 256 consecutive HTML line-break tags with only
whitespace now produce bounded protocol feedback through the existing malformed
tool-call recovery path. The current provider stream closes; an interrupted
client is retired before another iteration can reuse it. Ordinary text, tool
argument bodies and short formatting retain their existing behavior. This adds no execution deadline and
does not cancel accepted tasks. Tests of the bridge and its recovery loop are
supporting evidence; final-source model acceptance remains a separate gate.
