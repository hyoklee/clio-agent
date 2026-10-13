"""Submit-audit helpers for the CLIO agent loop (ClioReAct)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any

import dspy
import pydantic
from dspy.lm15 import ToolCallPart

from clio_agent.gact.agents.dspy_native_tool import ClioNativeTool

TURN_YIELD_METADATA = {"ask_user": "pending_ask_user", "plan_exit": "pending_plan_exit"}


def pending_turn_yield(calls: Sequence[ToolCallPart]) -> str:
    """Yield only after the interaction owner accepted a question or plan exit.

    A rejected call remains an ordinary tool error. The unsurfaced metadata
    proves acceptance; the post-forward boundary creates the visible interaction.
    """
    from clio_agent.gact import context

    names = {call.name for call in calls}
    if not names.intersection(TURN_YIELD_METADATA):
        return ""
    sessions = getattr(getattr(context.active_app(), "state", None), "sessions", None)
    sid = context.active_session_id()
    session = sessions.get(sid) if sessions is not None and sid else None
    metadata = getattr(session, "metadata", None)
    if not isinstance(metadata, Mapping):
        return ""
    for tool_name, key in TURN_YIELD_METADATA.items():
        pending = metadata.get(key)
        if (
            tool_name in names
            and isinstance(pending, Mapping)
            and pending
            and not pending.get("surfaced")
        ):
            return tool_name
    return ""


def tool_names(tools: Iterable[Any]) -> list[str]:
    """Return stable names from DSPy tool-like objects."""

    return [name for tool in tools if (name := str(getattr(tool, "name", "") or "").strip())]


def active_react_scope_safe() -> str:
    """Return the active ReAct scope, or an empty value outside a live turn."""
    try:
        from clio_agent.gact import context as _ctx  # noqa: PLC0415

        return _ctx.active_react_scope()
    except Exception:  # noqa: BLE001 - scope is optional off-turn
        return ""


def record_submit_audit(
    reason: str,
    *,
    agent_id: str,
    field: str,
    text: str,
    suppressed: bool,
) -> None:
    """Emit one queryable V2-path stream-audit record."""
    from clio_agent.runtime.stream_audit import stream_audit  # noqa: PLC0415

    stream_audit(
        "bridge.contract_field",
        agent_id=agent_id or "",
        field=field,
        chunk_len=len(text),
        visible=False,
        duplicate_suppressed=suppressed,
        duplicate_reason=reason,
        head=text[:120],
        full_text=text[:12000],
    )


def submit_tool(signature: Any) -> dspy.Tool:
    """The reserved ``submit`` tool: its args are the signature's outputs.

    An output field declared with a Pydantic default may be omitted (the default is
    filled -- the author declared it droppable); every other field is required.
    """
    output_fields = signature.output_fields
    if "assignment_disposition" in output_fields:
        raise ValueError(
            "assignment_disposition is reserved for orchestration, not signature output"
        )
    names = list(output_fields)
    defaults = {
        name: default
        for name, field in output_fields.items()
        for has_default, default in [_declared_default(field)]
        if has_default
    }

    def submit(**kwargs: Any) -> dict[str, Any]:
        missing = [n for n in names if n not in kwargs and n not in defaults]
        if missing:
            raise ValueError(f"Missing required final output field(s): {', '.join(missing)}")
        disposition = kwargs.pop("assignment_disposition", None)
        if disposition is not None:
            from clio_agent.gact.context import active_app, active_session_id, active_turn_id

            app = active_app()
            if app is not None:
                set_assignment_disposition(app, active_session_id(), active_turn_id(), disposition)
            elif disposition not in {"yield", "complete"}:
                raise ValueError("assignment_disposition must be yield or complete")
        return {n: kwargs[n] if n in kwargs else defaults[n] for n in names}

    return ClioNativeTool(
        submit,
        name="submit",
        desc=(
            "Submit the final outputs for the task. Use it only when these structured "
            "outputs are required; otherwise reply without calling a tool. "
            "assignment_disposition controls orchestration: yield preserves this assignment; "
            "complete finishes it even with accepted background work. Omission yields while "
            "work or input is pending, otherwise completes. Task results can wake you later."
        ),
        args={
            **{
                name: {
                    **_json_schema(field.annotation),
                    **({"default": defaults[name]} if name in defaults else {}),
                }
                for name, field in output_fields.items()
            },
            "assignment_disposition": {
                "type": ["string", "null"],
                "enum": ["yield", "complete", None],
                "default": None,
            },
        },
        arg_types={
            **{name: field.annotation for name, field in output_fields.items()},
            "assignment_disposition": str | None,
        },
    )


def _declared_default(field: Any) -> tuple[bool, Any]:
    """``(True, default)`` for an output field declared with a Pydantic default."""
    from pydantic_core import PydanticUndefined  # noqa: PLC0415

    default = getattr(field, "default", PydanticUndefined)
    if default is not PydanticUndefined:
        return True, default
    factory: Callable[[], Any] | None = getattr(field, "default_factory", None)
    if factory is not None:
        return True, factory()
    return False, None


def _json_schema(annotation: Any) -> dict[str, Any]:
    try:
        return pydantic.TypeAdapter(annotation).json_schema()
    except (pydantic.PydanticSchemaGenerationError, TypeError, ValueError):
        return {"type": "string"}
