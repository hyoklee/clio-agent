"""Legacy MCP elicitation schema, trusted URL and transport helpers.

The retired Question mirrors and answer/resume policy are removed. Production
Question commands will bind this protocol translation to the common Core record.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from clio_agent.gact.elicitation_correlation import invocation_with_request_correlation
from clio_agent.gact.elicitation_schema import (
    ELICITATION_QUESTION_SOURCE,
    FormTranslation,
    build_form_content,
    build_form_metadata,
    build_url_metadata,
    check_elicitation_answer,
    check_url_trust,
    default_answer_metadata,
    translate_form_schema,
    validate_elicitation_answer,
)
from clio_agent.gact.permission_delivery import attended_session_id
from clio_agent.gact.types import UserQuestion, UserQuestionOption
from clio_agent.tools.mcp_handlers import MCPClientCapabilities, MCPInvocationContext

logger = logging.getLogger(__name__)

__all__ = [
    "ELICITATION_QUESTION_SOURCE",
    "ELICITATION_REASONS",
    "FormTranslation",
    "check_elicitation_answer",
    "check_url_trust",
    "make_elicitation_client",
    "make_elicitation_hook",
    "resolve_elicitation",
    "stamp_question_routing_fields",
    "translate_form_schema",
    "validate_elicitation_answer",
]


#: Park timeout (permission-gate-style human window); expiry -> typed ``cancel``.
DEFAULT_ELICITATION_TIMEOUT_S = 600.0

#: Typed degrade/reject reason catalog (``stream_fallback`` style) — never silent.
ELICITATION_REASONS: dict[str, str] = {
    "elicitation_no_session": "no CLIO session resolved for the elicitation; declined",
    "elicitation_schema_not_object": "form schema is not a flat JSON object schema; declined",
    "elicitation_schema_not_flat": "form schema nests objects/arrays (not flat); declined",
    "elicitation_unsupported_field_type": "form schema field type is unsupported; declined",
    "elicitation_url_not_declared": "url-mode elicitation arrived but url was not advertised; declined",
    "elicitation_url_untrusted_origin": "url-mode elicitation origin is not on the trust list; declined",
    "elicitation_url_insecure_scheme": "url-mode elicitation is not https; declined",
    "elicitation_wait_timeout": "no answer within the elicitation window; cancelled",
    "elicitation_unknown_mode": "elicitation mode is neither form nor url; declined",
    "elicitation_task_identity_invalid": "task input owner or stored question is ambiguous; declined",
}


def _record_reason(reason: str, **fields: Any) -> None:
    """Log a typed elicitation degrade/reject reason (never silent)."""

    detail = ELICITATION_REASONS.get(reason, reason)
    logger.info(
        "elicitation degraded reason=%s detail=%s %s",
        reason,
        detail,
        " ".join(f"{k}={v!r}" for k, v in fields.items()),
    )


# --- Async-safe park / resolve ---


@dataclass(frozen=True)
class ElicitResolution:
    """The user's decision, translated back toward an SDK ``ElicitResult``."""

    action: Literal["accept", "decline", "cancel"]
    content: dict[str, Any] | None = None


#: Guards lazy creation of the per-app waiter registry AND every register/pop, so
#: two worker loops racing the first elicitation cannot create rival dicts (#1113
#: finding 4). The registry is a plain dict once created; all mutation holds this.
_WAITERS_LOCK = threading.Lock()

_WaiterEntry = tuple["asyncio.Future[ElicitResolution]", asyncio.AbstractEventLoop]


def _waiters(app: Any) -> dict[str, _WaiterEntry]:
    """Return the per-app elicitation waiter registry (thread-safe first use).

    Maps a pending question id to the parked future and the loop that awaits it.
    Double-checked locking makes concurrent first registrations converge on ONE
    dict rather than overwriting ``app.state`` with rival dicts (finding 4).
    """

    registry = getattr(app.state, "elicitation_waiters", None)
    if registry is None:
        with _WAITERS_LOCK:
            registry = getattr(app.state, "elicitation_waiters", None)
            if registry is None:
                registry = {}
                app.state.elicitation_waiters = registry
    return registry


def _register_waiter(app: Any, question_id: str, entry: _WaiterEntry) -> None:
    registry = _waiters(app)  # resolve/create OUTSIDE the item lock (non-reentrant)
    with _WAITERS_LOCK:
        registry[question_id] = entry


def _pop_waiter(app: Any, question_id: str) -> _WaiterEntry | None:
    registry = _waiters(app)  # resolve/create OUTSIDE the item lock (non-reentrant)
    with _WAITERS_LOCK:
        return registry.pop(question_id, None)


def _safe_set(future: "asyncio.Future[ElicitResolution]", resolution: ElicitResolution) -> None:
    if not future.done():
        future.set_result(resolution)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def resolve_elicitation(app: Any, question: UserQuestion) -> bool:
    """Resolve a parked elicitation from the shared answer/cancel route.

    Returns ``True`` when ``question`` was an in-flight elicitation whose parked call
    was woken (cross-loop-safe), ``False`` otherwise. The resolution is derived from
    the already-updated row and delivered to the parked future on its owning loop.
    """

    waiter = _pop_waiter(app, question.id)
    if waiter is None:
        return False
    future, loop = waiter
    resolution = _resolution_from_question(question)
    try:
        loop.call_soon_threadsafe(_safe_set, future, resolution)
    except RuntimeError as exc:  # owning loop already closed (worker torn down)
        logger.warning(
            "elicitation resolve dropped reason=owner_loop_closed question_id=%s error=%r",
            question.id,
            exc,
        )
        return False
    return True


def _resolution_from_question(question: UserQuestion) -> ElicitResolution:
    """Map an answered/cancelled UserQuestion to an SDK-shaped resolution."""

    if question.status in {"cancelled", "expired"}:
        return ElicitResolution(action="cancel")
    elicitation = question.metadata.get("elicitation") or {}
    # An explicit decline rides the answer metadata (the user rejected the ask).
    if str(question.answer_metadata.get("elicitation_action") or "") == "decline":
        return ElicitResolution(action="decline")
    if elicitation.get("mode") == "url":
        # URL consent carries no form content; accept == the user consented.
        return ElicitResolution(action="accept", content={})
    fields = elicitation.get("fields") or []
    content = build_form_content(
        fields,
        selected_options=question.selected_options,
        answer=question.answer,
        answer_metadata=question.answer_metadata,
    )
    return ElicitResolution(action="accept", content=content)


# --- The handler + client construction ---


def _new_question(
    session_id: str,
    *,
    prompt: str,
    kind: str,
    options: list[UserQuestionOption],
    metadata: dict[str, Any],
    source: str = ELICITATION_QUESTION_SOURCE,
    owner_session_id: str = "",
    attended_session_id: str = "",
    answer_metadata: dict[str, Any] | None = None,
    audience: str | None = None,
) -> UserQuestion:
    from clio_agent.gact.runtime.globals import _new_question_id  # noqa: PLC0415

    now_iso = datetime.now(timezone.utc).isoformat()
    return UserQuestion(
        id=_new_question_id(),
        session_id=session_id,
        owner_session_id=owner_session_id or session_id,
        attended_session_id=attended_session_id or session_id,
        prompt=prompt,
        status="pending",
        kind=kind,  # type: ignore[arg-type]
        options=options,
        created_at=now_iso,
        updated_at=now_iso,
        source=source,
        metadata=metadata,
        # SEP-1034: a form's declared defaults pre-populate this PENDING
        # question's answer surface (see elicitation_schema.default_answer_metadata).
        answer_metadata=answer_metadata or {},
        # #1309 C1-S7: the server's own declared audience hint (``None`` unless
        # the caller resolved it to exactly "agent" — see agent_elicitation.audience_hint).
        audience=audience,  # type: ignore[arg-type]
    )


def _build_elicit_result(resolution: ElicitResolution) -> Any:
    from fastmcp.client.elicitation import ElicitResult  # noqa: PLC0415

    return ElicitResult(action=resolution.action, content=resolution.content)


def make_elicitation_hook(
    app: Any,
    invocation: MCPInvocationContext,
    *,
    url_trusted_origins: Sequence[str] = (),
) -> Any:
    """Build the elicitation hook bound to ONE invocation (correlation identity).

    Matches :class:`~clio_agent.tools.mcp_handlers.ElicitationHook`; ignores the
    dispatcher's ``context`` because this closure already carries its invocation (one
    client per call) — the correct correlation on the per-call execution path.
    """

    async def hook(
        context: Any,
        message: str,
        response_type: Any,
        params: Any,
        request_context: Any,
    ) -> Any:
        correlated = invocation_with_request_correlation(invocation, request_context, app=app)
        return await handle_elicitation(
            app, correlated, message, params, url_trusted_origins=url_trusted_origins
        )

    return hook


def _resolve_trusted_origins(explicit: Sequence[str] | None) -> tuple[str, ...]:
    """Resolve the url-mode trust allow-list (explicit arg else config)."""

    from clio_agent.gact.elicitation_config import trusted_origins
    return trusted_origins(explicit)


def make_elicitation_client(
    app: Any,
    transport: Any,
    namespace: str = "",
    tool_name: str = "",
    *,
    invocation: MCPInvocationContext | None = None,
    url_trusted_origins: Sequence[str] | None = None,
    client_cls: Any = None,
) -> Any:
    """Build a per-call, elicitation-capable execution client (#1113).

    Wires the handler bound to ``invocation`` (per-call correlation); declares the
    capability at served granularity (form always; url only with a configured trust
    list). Keeps NORMAL (auto) era negotiation -- a legacy server negotiates legacy
    and the handler fires (SEP-2577). A DIRECT, unmirrored connect (#1201): classified
    + recorded under ``namespace`` the moment it connects (see mcp_connection_era.py).
    """

    from clio_agent.tools.mcp_runtime import MCPClientHandlers, make_mcp_client  # noqa: PLC0415

    origins = _resolve_trusted_origins(url_trusted_origins)
    if invocation is None:
        from clio_agent.gact.runtime.globals import _resolve_tool_session  # noqa: PLC0415

        try:
            sid = _resolve_tool_session(app)[0]
        except Exception:  # noqa: BLE001 - app-less/minimal caller: no session ctx
            sid = ""  # downstream hook emits the typed ``elicitation_no_session``
        invocation = MCPInvocationContext(
            invocation_id=f"{namespace}.{tool_name}" if namespace or tool_name else "elicit",
            session_id=sid,
            namespace=namespace or None,
            tool_name=tool_name or None,
        )
    hook = make_elicitation_hook(app, invocation, url_trusted_origins=origins)
    capabilities = MCPClientCapabilities(elicitation_form=True, elicitation_url=bool(origins))
    return make_mcp_client(
        transport,
        handlers=MCPClientHandlers(elicitation=hook),
        capabilities=capabilities,
        client_cls=client_cls,
        server_id=namespace,
    )
