"""Durable defer at every yield point (P2.6, epic #1031 Pillar 2).

A hook may return ``defer`` at three yield points. ``defer`` is a *governance*
outcome — "suspend this operation, accept the decision from an OUT-OF-BAND channel
(an API resolve / loop-inbox), resume when approved" — deliberately distinct from
"postpone the work". It NEVER silently drops or auto-approves: every defer persists a
pending approval (typed, surfaced) and blocks the operation until it is resolved from
anywhere.

This module is the ONE owner of the defer protocol (no accretion into
``permission_gate`` / ``turn`` / ``stop_loop``, which only call in):

* **PreToolUse defer — the headline (within-session durable).** It GENERALIZES the
  existing parked permission gate (``permission_gate._make_permission_gate`` already
  blocks a tool call mid-step on a ``threading.Event``). :func:`park_pretool_defer`
  registers a persisted pending-approval row (the SAME ``app.state.permissions`` +
  ``app.state.permission_events`` store the interactive gate uses — no new store,
  RULE 4) and parks the executor thread on that event with the interactive gate's
  ~600s→deny timeout LIFTED to a long, configurable bound. An out-of-band
  ``POST /v1/permissions/{pid}`` resolve (routed through
  ``permission_gate.resolve_permission``) wakes the parked call: ``allow`` runs the
  tool (or the ``modify``/``synthesize`` the approval carries); ``deny`` returns a
  typed deny to the model. The paused call resumes when approved from anywhere.

* **Turn-ending defer (Stop / UserPromptSubmit).** These are turn-ending yields, so
  they do NOT hold a thread — they ride the #1031 deferred-resume fold exactly like
  ``plan_exit`` (P1.4): :func:`suspend_turn_defer` persists a pending-approval row +
  flips the session to ``waiting_user``; the SAME ``resolve_permission`` path, on
  resolving a turn-defer row, calls :func:`resume_turn_defer`, which stages a new turn
  (approve) or the event-specific tighten (deny) via the loop-inbox /
  ``start_background_user_turn`` seam. No held thread, no new store.

* **Cross-restart durability (rides the replay substrate).** Every defer additionally
  mirrors its pending state onto ``session.metadata`` (:data:`HOOK_DEFER_PENDING_META`,
  the #948 AgentTask no-fifth-store projection) so it survives a process restart. See
  the module residual note below and ``docs/design/governance-surfaces-2026-07.md``
  (P2.6): full deterministic REPLAY-to-defer-point resume of a mid-loop PreToolUse
  across a restart is built on the P2.3 tool-synthesize + P2.4 dspy.LM-synthesize
  recording; the durable pending surface + resolvability land here, the replay-resume
  rehydration is the flagged residual.

Invariants (all enforced here): a defer never silently drops or auto-approves (a
persisted, typed pending row); the parked PreToolUse call never holds a thread
forever unbounded (a configurable long bound → fail-safe deny, never a silent
auto-approve; the thread-occupancy tradeoff is documented on
:func:`defer_timeout_s`); ``deny`` beats ``defer`` (the merge in ``wire.py`` and the
policy-deny-before-park check in ``permission_gate`` enforce tighten-only); a resume
applies the approved decision EXACTLY ONCE (``resolve_permission`` is idempotent — the
row flips to ``resolved`` and a second resolve is a no-op — and the ``threading.Event``
fires once); reads are never gated (this is only ever reached after the gate's
``is_read_only`` fast-allow).
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from clio_agent.gact.events import Event
from clio_agent.gact.hooks.wire import record_hook_reason
from clio_agent.gact.permission_delivery import publish_permission_event
from clio_agent.gact.runtime.retention import enforce_dict_bound

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Row kinds + typed reasons + the durable-surface session.metadata key.          #
# --------------------------------------------------------------------------- #

#: ``permission`` row ``kind`` for a PreToolUse defer parked on the executor thread.
PRETOOL_DEFER_KIND = "pretool_defer"

#: ``permission`` row ``kind`` for a turn-ending defer (Stop / UserPromptSubmit) that
#: suspended the session (no held thread) and resumes as a new turn on resolve.
TURN_DEFER_KIND = "turn_defer"

#: The audit ``reason`` stamped on a pending defer row so the ledger attributes the ask
#: to the defer path (never a silent default), mirroring ``REASON_AI_REVIEW_*``.
REASON_HOOK_DEFER = "hook_defer_pending"

#: ``session.metadata`` key: the durable cross-restart mirror of the pending defers for
#: this session — ``{pid: {kind, event, tool_name, created_at, ...}}`` (no fifth store,
#: the #948 AgentTask projection pattern). Written when a defer parks/suspends and
#: pruned when it resolves/times out, so a restart can see (and a future replay slice
#: rehydrate) what was outstanding.
HOOK_DEFER_PENDING_META = "hook_defer_pending"

#: Turn metadata flag carried on a resumed turn so the re-fired turn-ending hook does
#: not re-defer the SAME just-approved yield (the once-gate for turn-ending resume,
#: analogous to plan_exit's constraint-lift). Read by the UserPromptSubmit /Stop seams.
HOOK_DEFER_RESUME_META = "hook_defer_resume"

_DEFER_TIMEOUT_DEFAULT_S = 86400.0  # 24h — a long bound, not "no bound" (thread-occupancy).


def defer_timeout_s() -> float:
    """Return the configurable bound a parked PreToolUse defer waits before fail-safe deny.

    Read live from :mod:`clio_agent.conf` (``hooks.defer_timeout`` /
    ``CLIO_HOOKS_DEFER_TIMEOUT``, default 24h) so a deployment or a test can tune it
    without a code change.

    **Thread-occupancy tradeoff (documented, deliberate):** a within-session PreToolUse
    defer parks the tool-executor thread on a ``threading.Event`` for up to this bound,
    exactly as the interactive gate parks it for ~600s. The bound is LONG (so a human
    can take their time) but never infinite — an unresolved defer is released and DENIED
    fail-safe (:data:`hook_defer_timeout`), never silently auto-approved and never a
    thread pinned forever. The cross-restart path (which releases the thread entirely
    and resumes by replay) is the substrate answer to a defer that outlives the process.
    """

    from clio_agent import conf  # noqa: PLC0415 - avoid import cycle at module load

    value = conf.resolve(
        "hooks.defer_timeout",
        env="CLIO_HOOKS_DEFER_TIMEOUT",
        default=_DEFER_TIMEOUT_DEFAULT_S,
        cast=conf.as_float,
    )
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        seconds = _DEFER_TIMEOUT_DEFAULT_S
    # A non-positive bound would mean "deny immediately", collapsing defer into deny;
    # clamp to a small positive floor so the pending row is still surfaced+resolvable.
    return seconds if seconds > 0 else _DEFER_TIMEOUT_DEFAULT_S


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_pending_meta(app: "FastAPI", sid: str, pid: str, info: dict[str, Any]) -> None:
    """Mirror a pending defer onto ``session.metadata`` (durable cross-restart surface)."""

    if not sid:
        return
    session = app.state.sessions.get(sid)
    existing = {}
    raw = getattr(session, "metadata", None) if session is not None else None
    if isinstance(raw, Mapping) and isinstance(raw.get(HOOK_DEFER_PENDING_META), Mapping):
        existing = dict(raw[HOOK_DEFER_PENDING_META])
    existing[pid] = info
    app.state.sessions.update(sid, metadata_patch={HOOK_DEFER_PENDING_META: existing})


def _clear_pending_meta(app: "FastAPI", sid: str, pid: str) -> None:
    """Prune a resolved/timed-out defer from the durable ``session.metadata`` mirror."""

    if not sid:
        return
    session = app.state.sessions.get(sid)
    raw = getattr(session, "metadata", None) if session is not None else None
    if not isinstance(raw, Mapping) or not isinstance(raw.get(HOOK_DEFER_PENDING_META), Mapping):
        return
    existing = dict(raw[HOOK_DEFER_PENDING_META])
    if pid in existing:
        existing.pop(pid, None)
        app.state.sessions.update(sid, metadata_patch={HOOK_DEFER_PENDING_META: existing})


def _publish_pending(app: "FastAPI", sid: str, row: dict[str, Any]) -> None:
    """Surface a pending defer so ANY client sees it (the interactive-gate event shape)."""

    if hasattr(app.state, "bus"):
        publish_permission_event(
            app,
            "permission.requested",
            owner_session_id=sid,
            payload=row,
        )
    try:
        from clio_agent.gact.runtime.globals import _emit_semantic_event  # noqa: PLC0415

        _emit_semantic_event(
            app,
            sid,
            "hook.defer.pending",
            status="waiting_user",
            summary=f"A {row.get('kind', 'defer')} hook deferred an operation for out-of-band approval.",
            actor={"hook": row.get("hook_event", "")},
            subject={"permission_id": row.get("id", "")},
            payload={
                "permission_id": row.get("id", ""),
                "kind": row.get("kind", ""),
                "hook_event": row.get("hook_event", ""),
                "reason": row.get("defer_reason", ""),
            },
        )
    except Exception as exc:  # noqa: BLE001 - observability, never fatal to parking a defer
        logger.warning(
            "hook.defer.pending semantic emit skipped reason=defer_emit_failed pid=%s err=%r",
            row.get("id", ""),
            exc,
        )


# --------------------------------------------------------------------------- #
# 1) PreToolUse defer — the headline within-session durable park.               #
# --------------------------------------------------------------------------- #


def park_pretool_defer(
    app: "FastAPI",
    *,
    sid: str,
    name: str,
    args: Mapping[str, Any],
    subject: str,
    outcome: Any,
) -> str:
    """Park a PreToolUse call a hook DEFERRED until it is resolved out-of-band (P2.6).

    Generalizes the interactive gate's parked-``threading.Event`` primitive: persist a
    pending-approval row (kind :data:`PRETOOL_DEFER_KIND`), block the executor thread
    on the row's event with the interactive timeout LIFTED to :func:`defer_timeout_s`,
    and return the resolved decision. Returns ``"allow"`` (the tool runs — the
    interceptor consumes any modify/synthesize the approval carries), a
    ``DenyDecision`` (a typed deny reaches the model), or a fail-safe ``"deny"`` on
    timeout / no-session (never a silent auto-approve).

    Caller contract: the gate has already cleared the per-call intercept stash and
    established (deny beats defer) that no policy denies this call; this function owns
    stashing the final intercept for the SAME-thread interceptor that runs next.
    """

    from clio_agent.gact.hooks.intercept import stash_pre_tool_intercept  # noqa: PLC0415

    if not sid:
        # Fail-safe: a defer with nowhere to persist the approval is a DENY, never a
        # silent auto-approve (mirrors the interactive gate's no-session→deny).
        record_hook_reason("hook_defer_no_session", event="PreToolUse", tool_name=name)
        stash_pre_tool_intercept(None)
        return "deny"

    defer_reason = str(getattr(outcome, "reason", "") or "") or (
        f"tool call {name!r} was deferred by a PreToolUse hook for out-of-band approval"
    )
    pid = f"perm_{uuid.uuid4().hex[:12]}"
    evt = threading.Event()
    row: dict[str, Any] = {
        "id": pid,
        "session_id": sid,
        "kind": PRETOOL_DEFER_KIND,
        "hook_event": "PreToolUse",
        "tool_call": {"tool_name": name, "input": dict(args)},
        "summary": f"{subject} {name!r} deferred by a PreToolUse hook (awaiting out-of-band approval)",
        "defer_reason": defer_reason,
        "created_at": _now_iso(),
        "status": "pending",
        "reason": REASON_HOOK_DEFER,
    }
    app.state.permissions[pid] = row
    app.state.permission_events[pid] = evt
    enforce_dict_bound(app, app.state.permissions, "permissions", session_id=sid)
    _record_pending_meta(
        app,
        sid,
        pid,
        {
            "kind": PRETOOL_DEFER_KIND,
            "hook_event": "PreToolUse",
            "tool_name": name,
            "created_at": row["created_at"],
        },
    )
    _publish_pending(app, sid, row)

    resolved = evt.wait(timeout=defer_timeout_s())
    _clear_pending_meta(app, sid, pid)
    if not resolved:
        # Bounded (never infinite) — release the parked thread and DENY fail-safe.
        row["status"] = "timeout"
        record_hook_reason(
            "hook_defer_timeout", event="PreToolUse", tool_name=name, permission_id=pid
        )
        stash_pre_tool_intercept(None)
        return "deny"

    action = str(row.get("action", "deny") or "deny")
    if action in {"allow", "allow_session", "allow_workspace"}:
        _stash_resolution_intercept(row)
        return "allow"

    # deny (or anything non-allow): a typed deny to the model — never a silent drop.
    record_hook_reason("hook_defer_denied", event="PreToolUse", tool_name=name, permission_id=pid)
    stash_pre_tool_intercept(None)
    from clio_agent.gact.permission_gate import DenyDecision  # noqa: PLC0415

    return DenyDecision(
        str(row.get("defer_deny_message") or "")
        or f"tool call {name!r} was DENIED out-of-band after a PreToolUse defer"
    )


def _stash_resolution_intercept(row: Mapping[str, Any]) -> None:
    """Apply the modify/synthesize an APPROVED defer may carry to the interceptor stash.

    The approver may resolve a deferred tool call with ``allow`` alone (run the tool
    with its original args) OR carry a ``modify`` (``resolution_input``) / ``synthesize``
    (``resolution_result``) the same way a PreToolUse hook's tagged-union does. This
    runs on the parked executor thread right before it returns ``"allow"``, so the
    context-local stash the interceptor reads next belongs to THIS call.
    """

    from clio_agent.gact.hooks.intercept import set_pre_tool_intercept  # noqa: PLC0415
    from clio_agent.tools.tool_hooks import InterceptDecision  # noqa: PLC0415

    if "resolution_result" in row:
        set_pre_tool_intercept(
            InterceptDecision(kind="synthesize", result=row.get("resolution_result"))
        )
        return
    modified = row.get("resolution_input")
    if isinstance(modified, Mapping):
        set_pre_tool_intercept(InterceptDecision(kind="modify", modified_args=dict(modified)))
        return
    set_pre_tool_intercept(None)


# --------------------------------------------------------------------------- #
# 2) Turn-ending defer (Stop / UserPromptSubmit) — suspend + deferred-resume.    #
# --------------------------------------------------------------------------- #


def suspend_turn_defer(
    app: "FastAPI",
    *,
    sid: str,
    hook_event: str,
    reason: str,
    resume_text: str,
    prev_status: str = "running",
    extra: Mapping[str, Any] | None = None,
) -> str | None:
    """Suspend a turn-ending yield a hook DEFERRED, persisting a resolvable approval.

    Rides the #1031 deferred-resume substrate exactly like ``plan_exit`` (no held
    thread): persist a pending-approval row (kind :data:`TURN_DEFER_KIND`) carrying the
    ``hook_event`` and the ``resume_text`` to re-drive on approval, flip the session to
    ``waiting_user``, and surface the pending approval. The SAME
    ``permission_gate.resolve_permission`` path detects the turn-defer kind on resolve
    and calls :func:`resume_turn_defer`. Returns the ``pid`` (or ``None`` when there is
    no session to suspend under — the caller then proceeds normally, never silent).
    """

    if not sid:
        return None
    pid = f"perm_{uuid.uuid4().hex[:12]}"
    row: dict[str, Any] = {
        "id": pid,
        "session_id": sid,
        "kind": TURN_DEFER_KIND,
        "hook_event": hook_event,
        "summary": f"{hook_event} hook deferred the turn (awaiting out-of-band approval)",
        "defer_reason": reason or f"{hook_event} hook deferred this turn for approval",
        "resume_text": resume_text,
        "created_at": _now_iso(),
        "status": "pending",
        "reason": REASON_HOOK_DEFER,
        "prev_status": prev_status,
    }
    if extra:
        row.update(dict(extra))
    app.state.permissions[pid] = row
    enforce_dict_bound(app, app.state.permissions, "permissions", session_id=sid)
    _record_pending_meta(
        app,
        sid,
        pid,
        {"kind": TURN_DEFER_KIND, "hook_event": hook_event, "created_at": row["created_at"]},
    )
    app.state.sessions.update(
        sid,
        status="waiting_user",
        metadata_patch={"pending_defer_permission_id": pid, "execution_gate": pid},
    )
    _publish_pending(app, sid, row)
    if hasattr(app.state, "bus"):
        app.state.bus.publish(
            Event(
                type="session.status_changed",
                session_id=sid,
                payload={
                    "session_id": sid,
                    "status": "waiting_user",
                    "prev_status": prev_status,
                    "pending_defer_permission_id": pid,
                },
            )
        )
    return pid


def resume_turn_defer(app: "FastAPI", row: Mapping[str, Any], action: str) -> None:
    """Record a resolved hook's input before releasing its admission gate."""
    import asyncio

    sid, pid = str(row.get("session_id") or ""), str(row.get("id") or "")
    if not sid or not pid:
        return
    owner = app.state.conversations
    approved = action in {"allow", "allow_session", "allow_workspace"}
    hook_event = str(row.get("hook_event") or "")

    def release() -> None:
        _clear_pending_meta(app, sid, pid)
        current = app.state.sessions.get(sid)
        if current is not None and current.metadata.get("pending_defer_permission_id") == pid:
            patch: dict[str, Any] = {"pending_defer_permission_id": ""}
            if current.metadata.get("execution_gate") == pid:
                patch["execution_gate"] = ""
            app.state.sessions.update(sid, metadata_patch=patch)
        owner.runner.signal(sid)

    def stage() -> None:
        if hook_event == "Stop":
            _resume_stop_defer(app, sid, row)
        else:
            _resume_user_prompt_defer(app, sid, row, approved)
        release()

    if hook_event == "Stop" and approved:
        assignment = owner.history.latest_assignment(sid)
        if assignment is None:
            raise ValueError("Deferred assignment is unavailable")

        async def finish() -> None:
            await owner.complete_deferred(sid, assignment.handle)
            await asyncio.to_thread(release)

        async def accept_completion() -> None:
            try:
                await finish()
            except Exception:
                if not owner.history.requires_recovery:
                    raise
                owner.recovery.defer("hook-completion:" + pid, finish)

        def register() -> None:
            identity = "hook-completion:" + pid
            if identity not in owner._controls:
                owner.retain_control(identity, asyncio.create_task(accept_completion()))

        owner._loop.call_soon_threadsafe(register)
        return
    try:
        stage()
    except Exception:
        if not owner.history.requires_recovery:
            raise

        async def retry() -> None:
            await asyncio.to_thread(stage)

        owner._loop.call_soon_threadsafe(owner.recovery.defer, "hook-resume:" + pid, retry)


def _stage_resume_turn(
    app: "FastAPI",
    sid: str,
    session: Any,
    text: str,
    metadata: dict[str, Any],
    *,
    event: str,
    question_id: str,
) -> None:
    """Persist resolved hook feedback; only TurnRunner admits its continuation."""
    from clio_agent.arc.task_types import MailItem

    if session is None:
        raise ValueError("Deferred session is unavailable")
    history = app.state.task_history
    with history._lock:
        content = history.write_content(
            sid,
            {
                "text": text,
                "metadata": {**metadata, "question_id": question_id, "hook_event": event},
            },
        )
        identity = "hook-resume:" + question_id
        previous = history._mail.get(sid, {}).get(identity)
        if previous is not None:
            if previous.content != content:
                raise ValueError("Deferred hook input identity was reused")
            return
        permission = app.state.permissions.get(question_id, {})
        history.record_mail(
            MailItem(
                id=identity,
                recipient_session=sid,
                kind="approval",
                content=content,
                created_at=str(permission.get("created_at") or _now_iso()),
            )
        )


def _resume_user_prompt_defer(
    app: "FastAPI", sid: str, row: Mapping[str, Any], approved: bool
) -> None:
    session = app.state.sessions.get(sid)
    if not approved:
        # Reject: the prompt was denied out-of-band; no turn runs.
        prev = str(row.get("prev_status") or "waiting_user")
        app.state.sessions.update(sid, status="idle")
        app.state.bus.publish(
            Event(
                type="session.status_changed",
                session_id=sid,
                payload={
                    "session_id": sid,
                    "status": "idle",
                    "prev_status": prev,
                    "reason": "user_prompt_defer_denied",
                },
            )
        )
        return
    resume_text = str(row.get("resume_text") or "")
    _stage_resume_turn(
        app,
        sid,
        session,
        resume_text,
        {HOOK_DEFER_RESUME_META: True},
        event="user_prompt_defer.resumed",
        question_id=str(row.get("id") or ""),
    )


def _resume_stop_defer(app: "FastAPI", sid: str, row: Mapping[str, Any]) -> None:
    """Queue a denied Stop as feedback through the regular model-input boundary."""
    session = app.state.sessions.get(sid)
    feedback = str(row.get("resume_text") or row.get("defer_reason") or "").strip() or (
        "A Stop hook reported the task is not complete; continue working."
    )
    _stage_resume_turn(
        app,
        sid,
        session,
        feedback,
        {"stop_defer_redrive": True},
        event="stop_defer.redriven",
        question_id=str(row.get("id") or ""),
    )
