"""Forward-orchestration seam for the GACT turn engine (#767 Phase B).

Slice 5 of the ``turn.py`` decomposition: the block that resolves the turn's
active agent, builds its DSPy module and runs its ``forward`` lives here as
:func:`forward_turn`, a free function taking
:class:`~clio_agent.gact.turn_state.TurnState` first (the gact seam convention).

:func:`forward_turn`:

* resolves ``state.active_agent_id`` / ``state.invocation_agent_id`` IN PLACE (the
  live token emitter bound over ``state`` before this seam reads them late);
* runs the dynamic-agent (blueprint/prompt/tool) module's forward ONCE in the
  turn's forward executor (live text streams through the LM token hooks), setting
  ``state.prompt_resolution`` / ``state.dynamic_agent_used`` / ``state.agent_runtime``
  / ``state.pred`` as the original body did, and returns ``state.pred``. A react
  main routes to its declared children by CALLING the spawn-runtime tools
  (``spawn_agent_task`` / ``wait_agent_tasks``), so ``state.pred`` is already the
  main's own answer — there is no post-forward settle/synthesis pass.

The #714 danger set (the agent-builder + blueprint-runner seams and the executable
session-agent constant) is resolved through ``app`` via a *function-local* import
so the ``app._X`` test monkeypatches keep intercepting with zero test edits; the
cooperative-cancel + no-progress watchdog is reached through
:mod:`clio_agent.gact.turn_watchdog`.
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING, Any, Callable, cast

from clio_agent.gact import context as _ctx
from clio_agent.gact import session_warmup
from clio_agent.gact.agents.composition import _apply_prompt_registry_to_agent
from clio_agent.gact.agents.resolution import (
    _agent_definition_uses_blueprint_runtime,
    _resolve_runtime_dynamic_agent,
    _runtime_active_agent_blueprint_agent_ids,
    _runtime_active_agent_blueprint_root_id,
    _runtime_active_agent_blueprint_rows,
    _runtime_effective_agent_blueprint_id,
    _runtime_effective_agent_blueprint_path,
)
from clio_agent.gact.catalog import _builtin_main_agent
from clio_agent.gact.evidence import _dynamic_agent_runtime_provenance
from clio_agent.gact.messaging import _prediction_summary
from clio_agent.gact.native_model_inputs import native_input_kwargs
from clio_agent.gact.off_loop import emit_semantic_event_async
from clio_agent.gact.providers.auth import _refresh_argonne_lm_token
from clio_agent.gact.runtime import bringup_timing
from clio_agent.gact.runtime.globals import (
    _async_tool_session_context,
    _BlueprintRootDisabled,
    _llm_provider_payload,
    _NoResolvableAgent,
    _session_agent_id,
    _tool_session_context,
    _UnsupportedSessionAgent,
)
from clio_agent.gact.runtime.type_parsing import _blueprint_module_kind
from clio_agent.gact.turn_reasoning import apply_turn_reasoning, record_turn_reasoning
from clio_agent.gact.turn_watchdog import await_turn_work, cancel_requested

if TYPE_CHECKING:
    from clio_agent.gact.turn_state import TurnState
    from clio_agent.gact.types import AgentDef
    from clio_agent.prompts import PromptRegistry


async def _run_turn_setup_off_loop(state: "TurnState", function: Callable[[], Any]) -> Any:
    """Run finite preparation off-loop and retire it before propagating cancellation."""
    from clio_agent.gact.off_loop import join_off_loop

    return await join_off_loop(function)


async def _run_module(state: "TurnState", module: Any, cancel: Callable[[], bool]) -> Any:
    """Run the production module in this session's exclusively owned turn worker."""
    from clio_agent.agent import cancellation_checker

    def forward() -> Any:
        with cancellation_checker(cancel), _tool_session_context(state.sid, lease_fleet=False):
            from clio_agent.errors import CancellationError

            if cancel():
                raise CancellationError("Session stopped before startup")
            with state.app.state.task_history.serialized():
                assignment = state.app.state.task_history.latest_assignment(state.sid)
                if assignment is None:
                    raise ValueError("Session assignment is unavailable before initialization")
                state.app.state.conversations.require_admission(assignment)
            # Hooks run on this session's existing worker. They never hold the
            # shared task writer, and Stop waits for their physical retirement.
            state.app.state.sessions.initialize(state.sid, cancel_event=state.turn_cancel_event)
            if cancel():
                raise CancellationError("Session stopped during startup")
            with state.app.state.task_history.serialized():
                state.app.state.conversations.require_admission(assignment)
            kwargs = {
                "question": state.enriched_text,
                "session_id": state.sid,
                "session_mode": state.sess.mode,
                "session_edit_mode": state.sess.edit_mode,
                "cancel_requested": cancel,
                **native_input_kwargs(
                    state.app,
                    state.sid,
                    module,
                    images=state.native_images,
                    files=state.native_files,
                ),
            }
            return module(**kwargs)

    return await state.app.state.turn_runner.run_sync(state.sid, forward)


async def forward_turn(state: "TurnState") -> Any:
    """Retain the workspace lease for this segment; no whole-turn executor pool."""
    async with _async_tool_session_context(state.sid):
        return await _forward_turn_leased(state)


def _apply_turn_model_selection(state: "TurnState", agent_def: "AgentDef") -> "AgentDef":
    """Overlay an accepted per-message/session route onto this turn's local agent.

    ``message_submission.accept_message`` already validated the selection (it
    executes only when the active LM serves it or the provider catalog holds live
    handshake evidence) and recorded the deciding layer on the user message. This
    copies that decision onto a LOCAL copy of the agent definition, so the routed
    model reaches the forward without mutating the stored agent.
    """

    source = str(state.user_msg.metadata.get("model_selection_source") or "global_active")
    raw = state.user_msg.metadata.get("effective_model")
    if source == "global_active" or not isinstance(raw, dict):
        return agent_def
    provider_id = str(raw.get("provider_id") or "").strip()
    model_id = str(raw.get("model_id") or "").strip()
    if not provider_id or not model_id:
        return agent_def
    metadata = dict(agent_def.metadata)
    metadata["turn_model_selection_source"] = source
    return agent_def.model_copy(
        update={
            "default_provider": provider_id,
            "default_model": model_id,
            "metadata": metadata,
        }
    )


async def _forward_turn_leased(state: "TurnState") -> Any:
    """Resolve the turn's agent, run its forward, settle delegations; return pred.

    Sets ``state.invocation_agent_id`` / ``state.active_agent_id`` /
    ``state.agent_runtime`` / ``state.prompt_resolution`` /
    ``state.dynamic_agent_used`` / ``state.expert_handoffs`` and returns the
    prediction (``state.pred``). See the module docstring for TRICKY #1/#2.
    """

    # #714 DANGER SET: the agent-builder + blueprint-runner seams are resolved
    # through ``app`` via a *function-local* import so the ~83 ``app._X`` test
    # monkeypatches (which retarget these at call time) keep working with zero
    # test edits. ``_EXECUTABLE_SESSION_AGENT_IDS`` is an ``app``-owned module
    # constant read here too.
    from clio_agent.gact.app import (  # noqa: PLC0415
        _EXECUTABLE_SESSION_AGENT_IDS,
        _build_blueprint_dspy_module,
        _build_prompt_user_agent_module,
        _build_tool_user_agent_module,
    )

    # Cooperative-cancel probe as a zero-arg predicate for the module + checker.
    cancel_cb = partial(cancel_requested, state)

    # #1215 S5: NESTED under workspace.lease (see forward_turn) -- resolves the
    # active agent + builds its DSPy module; end_phase call sits right after the
    # module build below, before the actual LLM request dispatch begins.
    # The servers this turn may call start alongside it; the turn itself waits only
    # for tool listings, and a call only for its own server.
    session_warmup.release_session_fleet(state.sid)  # the lease below holds it now
    session_warmup.start_session_warmup(state.app, state.sid, trigger="turn_started")
    bringup_timing.timer_for_session(state.app, state.sid).start_phase("blueprint.resolve")
    session_agent_id = _session_agent_id(state.sess)
    state.active_agent_id = state.turn_agent_id or session_agent_id
    active_blueprint_id = _runtime_effective_agent_blueprint_id(state.app, state.sid)
    active_blueprint_root_id = _runtime_active_agent_blueprint_root_id(state.app, state.sid)
    active_blueprint_agent_ids = _runtime_active_agent_blueprint_agent_ids(state.app, state.sid)
    if (
        not state.turn_agent_id
        and active_blueprint_root_id
        and (
            state.active_agent_id in {"", "main", "default"}
            or state.active_agent_id == active_blueprint_id
        )
    ):
        # Session creation may persist the selected Agent Blueprint's catalog id
        # as ``session.agent.id`` while activation resolves its executable root
        # expert separately. The catalog id names the container, not an AgentDef;
        # translate it to the declared root instead of rejecting the correctly
        # activated blueprint as an unknown session agent.
        state.active_agent_id = active_blueprint_root_id
    if (
        active_blueprint_root_id
        and state.active_agent_id == active_blueprint_root_id
        and state.active_agent_id not in active_blueprint_agent_ids
    ):
        # #948 S4: the active blueprint's DECLARED root exists but is disabled
        # (validation errors — e.g. a pre-migration pack whose chain_of_thought
        # main declares children). Fail TYPED here: no silent substitute root,
        # no fall-through to the legacy planner (both observed on the live gate).
        rows = _runtime_active_agent_blueprint_rows(state.app, session_id=state.sid)
        root_errors = next(
            (list(row.validation_errors) for row in rows if row.id == active_blueprint_root_id),
            [],
        )
        blueprint_id = str(rows[0].metadata.get("agent_blueprint_id") or "" if rows else "")
        raise _BlueprintRootDisabled(
            active_blueprint_root_id,
            blueprint_id=blueprint_id,
            validation_errors=root_errors,
        )
    # BARE session (owner ruling 2026-08-05 + RULE 2): the session activated NO
    # blueprint (no id, no path — not merely "nothing resolved"), so it executes
    # the shipped builtin react main from code. An EXPLICITLY activated blueprint
    # that resolves nothing stays on the typed _NoResolvableAgent path below —
    # the builtin main never silently substitutes for a broken activation.
    run_builtin_main = (
        not active_blueprint_root_id
        and state.active_agent_id in _EXECUTABLE_SESSION_AGENT_IDS
        and not active_blueprint_id
        and _runtime_effective_agent_blueprint_path(state.app, state.sid) is None
    )
    if run_builtin_main:
        state.active_agent_id = "main"
    _ctx.set_primary_agent_id(state.active_agent_id)
    routing_mode = getattr(state.sess, "routing_mode", "auto") or "auto"
    state.invocation_agent_id = state.active_agent_id or "orchestrator"
    await emit_semantic_event_async(
        state.app,
        state.sid,
        "agent.invocation.started",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        status="running",
        summary=f"Invoking {state.invocation_agent_id}.",
        actor={"agent_id": state.invocation_agent_id},
        subject={"message_id": state.user_msg.id},
        payload={
            "routing_mode": routing_mode,
            "session_agent_id": session_agent_id,
            "turn_agent_id": state.turn_agent_id,
            "active_blueprint_root_id": active_blueprint_root_id,
            "active_blueprint_agent_ids": active_blueprint_agent_ids,
        },
    )
    from clio_agent.agent import cancellation_checker as _cancellation_checker  # noqa: PLC0415

    _refresh_argonne_lm_token(state.app.state.agent)
    # #1227 D2: re-discover the relay catalog once its TTL has elapsed instead
    # of trusting the boot-time snapshot forever -- a no-op read on every turn
    # until the TTL fires, so this is not a per-turn relay round trip.

    if (
        run_builtin_main
        or state.active_agent_id not in _EXECUTABLE_SESSION_AGENT_IDS
        or state.active_agent_id in active_blueprint_agent_ids
    ):
        prompt_registry_factory = getattr(state.app.state, "prompt_registry_for_request", None)
        prompt_registry = cast(
            "PromptRegistry | None",
            (
                prompt_registry_factory(session_id=state.sid)
                if callable(prompt_registry_factory)
                else None
            ),
        )
        if run_builtin_main:
            # The builtin main is code, not a discoverable definition: it is
            # materialized here (prompt registry applied like every resolved
            # agent), never via blueprint/pack discovery. A host that cannot
            # execute it fails TYPED at module build (_UnsupportedSessionAgent
            # from _dynamic_agent_tools) — never an empty assistant message.
            dynamic_agent: "AgentDef | None" = _apply_prompt_registry_to_agent(
                state.app, _builtin_main_agent(), prompt_registry=prompt_registry
            )
        else:
            dynamic_agent = _resolve_runtime_dynamic_agent(
                state.app,
                state.active_agent_id,
                session_id=state.sid,
                prompt_registry=prompt_registry,
            )
        if dynamic_agent is None:
            raise _UnsupportedSessionAgent(state.active_agent_id)
        dynamic_agent = _apply_turn_model_selection(state, dynamic_agent)
        # The message's own reasoning effort overrides the configured level for
        # this turn only (a local agent copy; see gact.turn_reasoning).
        dynamic_agent = apply_turn_reasoning(
            state.user_msg, dynamic_agent, app=state.app, session=state.sess
        )
        state.prompt_resolution = dict(dynamic_agent.metadata.get("prompt_resolution") or {})
        state.dynamic_agent_used = dynamic_agent
        dynamic_kind = (
            _blueprint_module_kind(dynamic_agent)
            if _agent_definition_uses_blueprint_runtime(dynamic_agent)
            else ""
        )
        execution_mode = (
            f"blueprint_{dynamic_kind}"
            if dynamic_kind
            else ("tool_agent" if dynamic_agent.tools else "prompt_agent")
        )
        state.agent_runtime = _dynamic_agent_runtime_provenance(
            state.app,
            dynamic_agent,
            execution_mode=execution_mode,
        )
        record_turn_reasoning(state.app, state.sid, state.turn_id, state.agent_runtime)
        await emit_semantic_event_async(
            state.app,
            state.sid,
            "agent.toolset.prepare.started",
            turn_id=state.turn_id,
            trace_id=state.trace_id,
            status="running",
            summary=f"Preparing tools for {dynamic_agent.id}.",
            actor={"agent_id": dynamic_agent.id},
            subject={"message_id": state.user_msg.id},
            payload={"agent_id": dynamic_agent.id, "tools": list(dynamic_agent.tools)},
        )
        # The keystone (set_turn_identity) already binds active_app() for the
        # whole turn, so no _gact_app_context wrapper is needed here.
        session_token = _ctx.set_session_id(state.sid)
        try:

            def build_module() -> Any:
                return (
                    _build_blueprint_dspy_module(state.app.state.agent, dynamic_agent)
                    if _agent_definition_uses_blueprint_runtime(dynamic_agent)
                    else (
                        _build_tool_user_agent_module(state.app.state.agent, dynamic_agent)
                        if dynamic_agent.tools
                        else _build_prompt_user_agent_module(state.app.state.agent, dynamic_agent)
                    )
                )

            module = await _run_turn_setup_off_loop(state, build_module)
        except Exception:
            await emit_semantic_event_async(
                state.app,
                state.sid,
                "agent.toolset.prepare.failed",
                turn_id=state.turn_id,
                trace_id=state.trace_id,
                status="failed",
                summary=f"Tool preparation failed for {dynamic_agent.id}.",
                actor={"agent_id": dynamic_agent.id},
                subject={"message_id": state.user_msg.id},
                payload={"agent_id": dynamic_agent.id, "tools": list(dynamic_agent.tools)},
            )
            raise
        finally:
            _ctx.reset(session_token)
        await emit_semantic_event_async(
            state.app,
            state.sid,
            "agent.toolset.prepare.completed",
            turn_id=state.turn_id,
            trace_id=state.trace_id,
            status="completed",
            summary=f"Tools ready for {dynamic_agent.id}.",
            actor={"agent_id": dynamic_agent.id},
            subject={"message_id": state.user_msg.id},
            payload={"agent_id": dynamic_agent.id, "tools": list(dynamic_agent.tools)},
        )
        # #1215 S5: blueprint resolution + module build are done; the LLM
        # request dispatch below is NOT part of blueprint.resolve.
        bringup_timing.timer_for_session(state.app, state.sid).end_phase("blueprint.resolve")
        llm_actor = {
            "agent_id": dynamic_agent.id,
            "agent_title": dynamic_agent.title,
            "source": dynamic_agent.source,
            "execution_mode": execution_mode,
        }
        llm_subject = {
            "prompt_id": dynamic_agent.prompt_id,
            "prompt_profile": dynamic_agent.prompt_profile,
            "message_id": state.user_msg.id,
        }
        await emit_semantic_event_async(
            state.app,
            state.sid,
            "llm.request.started",
            turn_id=state.turn_id,
            trace_id=state.trace_id,
            status="running",
            summary=f"LLM request started for {dynamic_agent.id}.",
            actor=llm_actor,
            subject=llm_subject,
            blueprint=dict(state.agent_runtime.get("agent_blueprint") or {}),
            provider=_llm_provider_payload(state.app, dynamic_agent.id),
            payload={
                "input": state.enriched_text,
                "prompt_resolution": state.prompt_resolution,
                "agent_runtime": state.agent_runtime,
                "native_image_count": len(state.native_images),
                "native_file_count": len(state.native_files),
            },
        )
        with _cancellation_checker(cancel_cb), _tool_session_context(state.sid, lease_fleet=False):
            state.pred = await await_turn_work(state, _run_module(state, module, cancel_cb))
        await emit_semantic_event_async(
            state.app,
            state.sid,
            "llm.response.completed",
            turn_id=state.turn_id,
            trace_id=state.trace_id,
            summary=f"LLM response completed for {dynamic_agent.id}.",
            actor=llm_actor,
            subject=llm_subject,
            blueprint=dict(state.agent_runtime.get("agent_blueprint") or {}),
            provider=_llm_provider_payload(state.app, dynamic_agent.id),
            payload=_prediction_summary(state.pred),
        )
    else:
        # #948 S4b: the agent id is in {"", "main", "default"} but the session
        # EXPLICITLY activated a blueprint (id/path set) that resolves no such
        # executable agent — e.g. an activation naming a blueprint that is
        # missing from disk or fully disabled. A bare session never reaches
        # here (it runs the builtin react main above); an explicit activation
        # must not be silently downgraded to the builtin main. The legacy
        # Tier-1 planner (ClioAgent.forward) that used to run here is DELETED,
        # so there is nothing to execute. Fail TYPED — never fall through to a
        # legacy pathway.
        raise _NoResolvableAgent(state.active_agent_id or session_agent_id)
    await emit_semantic_event_async(
        state.app,
        state.sid,
        "agent.invocation.completed",
        turn_id=state.turn_id,
        trace_id=state.trace_id,
        summary=f"{state.invocation_agent_id} returned a prediction.",
        actor={"agent_id": state.invocation_agent_id},
        subject={"message_id": state.user_msg.id},
        payload={
            "selected_expert": getattr(state.pred, "selected_expert", "") or "",
            "route_source": getattr(state.pred, "route_source", "") or "",
            "has_answer": bool(getattr(state.pred, "answer", "") or ""),
            "has_error_info": bool(getattr(state.pred, "error_info", None)),
        },
    )
    return state.pred
