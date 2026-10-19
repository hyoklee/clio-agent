# NDP tool activation qualification

NDP's six high-level native tools are no longer attached to every root agent.
An owned, connected NDP dataset or visible saved Endpoint in the executing
session's workspace enables them. The gate reads local records at each turn
build; it performs no account lookup, credential resolution or network discovery.
Disconnected/removed datasets and hidden Endpoints do not activate it. Another
workspace's connections and a shared account login do not activate it either.
Specialists retain their existing boundary: these tools are not auto-attached
to children.

The general connected-data tools and NDP skill metadata remain discoverable.
Initial setup uses **Attach > NDP**, then the next conversation turn receives
the tools. The skill, connection/status descriptions and NDP guide document that
bootstrap and lifecycle. The global product catalog still describes optional
NDP capabilities; it is separate from a session's actual model tool inventory.

## Real CLIO conversation

[Open the retained conversation](http://127.0.0.1:5219/workspaces/ws_0e67f0835686/sessions/sess_e71273330bc6).
All prompts were submitted through the actual web composer to Codex Sol.
No model responses or tool results were injected.

| Turn | Exact user request | Workspace state | Actual built tools | NDP tools |
| --- | --- | --- | ---: | ---: |
| 1 | What is 17 times 23? | No NDP dataset or Endpoint | 56 | 0 |
| 2 | What can my connected NDP service do? | Public CSV replay Endpoint connected | 62 | 6 |
| 3 | What is 19 times 27? | The sole Endpoint hidden | 56 | 0 |

Between turns 1 and 2, the test operator connected the existing public service
`https://vdc-192.chpc.utah.edu/api-stream` through the normal backend route in
this disposable test workspace, with authentication `none`. Between turns 2 and
3, that test connection was hidden. Existing user workspace connections were
unchanged. Existing NDP connections elsewhere on the same backend did not enable
the tools for turns 1 or 3.

In turn 2, the model independently loaded `work-with-ndp`, read connected-data
status, discovered the Endpoint's ten operations, and requested the active-stream
and CSV-file listings. Both public reads received individual Allow once approval.
Active streams returned an empty list. CSV-file listing returned the service's
previously recorded HTTP 500, which the final answer reported correctly. This
qualifies tool activation, discovery and removal, not successful CSV listing or
live stream delivery. The arithmetic turns returned 391 and 513.

The counts come from durable `agent.toolset.recorded` events emitted at the actual
instrumented agent-construction seam, not the product catalog or a UI fixture.
Evidence directory: `D:/CLIO-Develop/ndp-activation-20261018/`, including exact
prompts, the raw toolset names/calls/messages in `receipt.json`, public connection
records and an actual session-inventory screenshot. The conversation is idle;
the test Endpoint remains hidden.

## Regression checks

`uv run --no-sync pytest tests/test_gact/test_ndp_tool_activation.py tests/test_gact/test_connected_data_setup_tool.py tests/test_gact/test_tool_instrumentation.py tests/test_gact/test_agents_catalog.py -q`

**60 passed, no skips.** New cases construct actual ReAct function declarations
and cover source connect/disconnect/reconnect/removal, Endpoint connect/hide/
restore/removal through real local HTTP discovery, multiple active inputs,
workspace/principal/CLIO ownership isolation, missing context, child scoping,
credential/network-free activation, and completeness of the global catalog.
The first run exposed a test fixture using an unconfigured catalog; that fixture
was corrected before the complete passing run.

Ruff lint/format and Pyright passed for the changed Python files. Site check:
zero errors/warnings (three existing hints); build: 96 pages and all internal
links valid. No homepage files changed. The served preview backend was restarted
with this implementation after confirming all conversations were idle; existing
accounts, sessions and previews were preserved. Nothing merged or released.
