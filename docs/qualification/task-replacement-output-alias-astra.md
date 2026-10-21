**It was shipped. R2 requires a compatibility delegate for one release cycle.**

Introduced by `57ac35e1` (#1306), it is registered in the source of published **v0.9.2**, commit `4963211`, and remains present in `v0.9.5-beta.5.2`. This is a public tool contract, not branch-only work. [Published release](https://github.com/iowarp/clio-agent/releases/tag/v0.9.2), [released catalog registration](https://github.com/iowarp/clio-agent/blob/4963211fd11ab121bf02b1d4098ced3202b892e9/src/clio_agent/gact/agents/spawn_runtime_declarations.py#L170).

Recommended boundary:

- Add explicitly requested `get_agent_task_output(task_id)` to the existing compatibility builder, translating `task_id` to canonical `handle`.
- Use the same authorized result lookup and `_collected` path as `get_task_result`. Preserve the `CollectedTaskResult` notification identities through any response-field adaptation; acknowledgement remains at recipient-input commitment.
- Keep new default catalogs on `get_task_result`. Describe its bounded result/reference behavior accurately; do not retain the old unconditional “full output byte-for-byte” promise.
- Preserve pure digest tests. Rewrite catalog/getter tests around the compatibility contract, authorization, failed-task results, and durable collection. Retire registry-specific setup/assertions rather than restoring `get_agent_task_output_impl`, the old builder, or the registry.

The retained digest currently still emits `get_agent_task_output(task_id)`. Any newly emitted retrieval instructions should name the canonical tool and argument; the alias covers retained legacy instructions.

Read-only historical/source adjudication only; no tests or runtime acceptance claimed.
