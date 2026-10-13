"""Runtime state wiring for message intents and workspace resources."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from clio_agent import conf, paths
from clio_agent.gact.mcp_user_configuration import (
    McpUserConfigurationError,
    configured_web_remote_url,
)
from clio_agent.gact.resource_custody import ResourceStore
from clio_agent.gact.resource_delivery import ResourceDeliveryStore
from clio_agent.gact.resource_processing import (
    DocumentProcessorClient,
    ResourceConverterFactory,
    ResourceProcessingStore,
)
from clio_agent.gact.types import Message

AppendMessage = Callable[[Any, str, Message], None]
logger = logging.getLogger(__name__)


def initialize_composer_state(app: Any, session_store_path: Path) -> None:
    """Install the durable composer stores.

    Pending feedback is recovered into Core during application startup, after
    the confirmed writer and conversation operations are available.
    """

    state_root = session_store_path.parent
    max_resource_bytes = conf.resolve(
        "resources.max_bytes",
        env="CLIO_RESOURCE_MAX_BYTES",
        default=250 * 1024 * 1024,
        cast=conf.as_int,
    )
    app.state.resource_store = ResourceStore(
        root=(
            paths.user_data_dir() / "resources"
            if state_root == paths.server_state_dir()
            else state_root / "resources"
        ),
        max_resource_bytes=max_resource_bytes,
    )
    app.state.resource_delivery_store = ResourceDeliveryStore(
        state_root / "resource_deliveries.json"
    )
    local_processor_url = conf.resolve(
        "resources.document_processor_url",
        env="CLIO_DOCUMENT_PROCESSOR_URL",
        default="",
        cast=conf.as_str,
    )
    try:
        user_processor_url = configured_web_remote_url()
    except McpUserConfigurationError as exc:
        logger.warning("could not resolve saved Web Search document processor: %s", exc)
        user_processor_url = ""
    processor_url = user_processor_url or local_processor_url
    app.state.resource_processing_store = ResourceProcessingStore(app.state.resource_store)
    app.state.resource_converter_factory = ResourceConverterFactory(
        [DocumentProcessorClient(processor_url, max_resource_bytes=max_resource_bytes)]
    )


def register_composer_routes(app: Any, deps: Any) -> None:
    """Register the message-intent, resource, and provider-catalog routes.

    The A2UI routes are NOT registered here: ``build_app`` already owns that
    registration (and ``runtime.rework_state.initialize_a2ui_store`` owns the
    store), so re-registering them would duplicate the surface.
    """

    from clio_agent.gact.routes.message_intents import (  # noqa: PLC0415
        register_message_intent_routes,
    )
    from clio_agent.gact.routes.provider_catalog import (  # noqa: PLC0415
        register_normalized_provider_catalog_routes,
    )
    from clio_agent.gact.routes.resources import register_resource_routes  # noqa: PLC0415

    register_message_intent_routes(app, deps)
    register_resource_routes(app, deps)
    register_normalized_provider_catalog_routes(app, deps)
    app.state.redrive_message_queue = lambda sid: promote_queue_head(app, deps, sid)
    _install_composer_idle_hook(app, deps)


def session_autostart_suspended(app: Any, session_id: str) -> bool:
    """Whether future queued messages are paused, independently of sent feedback.

    Persist the pause across follow-up feedback turns and restarts. Legacy
    cancelled sessions without this metadata retain their previous queue pause.
    An explicit idle send resumes the queue; automatically delivered feedback
    does not. Already accepted steers remain eligible at the next idle boundary.
    """

    session = app.state.sessions.get(session_id)
    metadata = getattr(session, "metadata", {}) or {}
    return bool(
        metadata.get("composer_queue_paused", getattr(session, "status", "") == "cancelled")
    )


def stop_session_composer_autostart(app: Any, session_id: str) -> dict[str, Any]:
    """Pause future queued messages without suspending already submitted feedback.

    Stop cancels the current turn. Pending steers are separate human messages
    already accepted into the transcript, so they run after that turn releases
    its slot. Neither plane is deleted, and the future queue stays paused even
    after those feedback turns finish.
    """

    from clio_agent.gact.events import Event  # noqa: PLC0415

    intents = getattr(app.state, "message_intents", None)
    if intents is None:
        return {"reason": "composer_state_unavailable", "suspended": False}
    app.state.sessions.update(session_id, metadata_patch={"composer_queue_paused": True})
    summary = {
        "reason": "session_cancelled",
        "suspended": True,
        "queued_messages_paused": True,
        "pending_steers_suspended": False,
        "retained_pending_steers": len(intents.list_pending(session_id)),
        "retained_queued_messages": len(intents.list_queued(session_id)),
    }
    if summary["retained_pending_steers"] or summary["retained_queued_messages"]:
        app.state.bus.publish(
            Event(
                type="composer.autostart_suspended",
                session_id=session_id,
                payload={"session_id": session_id, **summary},
            )
        )
    return summary




def promote_queue_head(app: Any, deps: Any, session_id: str) -> None:
    """Compatibility hint; only TurnRunner admits queued conversation inputs."""
    app.state.turn_runner.request_input_admission(session_id)




def _blocked_heads(app: Any) -> dict[str, dict[str, Any]]:
    """Per-session record of a queue head that failed terminally, keyed by revision."""

    rows = getattr(app.state, "queue_blocked_heads", None)
    if not isinstance(rows, dict):
        rows = {}
        app.state.queue_blocked_heads = rows
    return rows


def _head_is_blocked(app: Any, session_id: str, head: Any) -> bool:
    """True when THIS head, at THIS revision, already failed terminally."""

    row = _blocked_heads(app).get(session_id)
    return bool(
        row and row.get("queued_message_id") == head.id and row.get("revision") == head.revision
    )


def _clear_blocked_head(app: Any, session_id: str) -> None:
    """Forget a session's blocked head (it promoted, or the queue emptied)."""

    _blocked_heads(app).pop(session_id, None)


def blocked_queue_head(app: Any, session_id: str) -> dict[str, Any] | None:
    """The queue head this session is frozen behind, if any (read-side helper)."""

    row = _blocked_heads(app).get(session_id)
    return dict(row) if row else None


def _typed_cause(exc: BaseException) -> dict[str, Any]:
    """Unwrap the typed error envelope acceptance raised, when there is one.

    The auto-promoter used to swallow the ``HTTPException`` acceptance raised
    into a generic ``queue_auto_promotion_failed``, so a client saw a bare
    "something went wrong" with a ``retry_on`` implying recovery -- while the
    manual ``POST .../promote`` door, which lets the exception through, showed the
    real reason. The two doors now agree: the typed cause rides the payload.
    """

    from fastapi import HTTPException  # noqa: PLC0415

    # The acceptance stack raises the SAME typed envelope in three carriers, and the
    # ``except Exception`` seam above sees all of them: an ``HTTPException`` whose
    # detail was already ``model_dump``-ed, one whose detail is still the envelope
    # MODEL, and a bare carrier holding an ``ErrorInfo`` on ``error_info``
    # (``_ContextFileAccessError``). Unwrapping only the first flattened the other
    # two to the exception class name.
    carried = _error_info_fields(getattr(exc, "error_info", None))
    if not isinstance(exc, HTTPException):
        if carried is not None:
            # No HTTP status of its own: this reason never reached a route boundary.
            return {"status_code": 0, **carried}
        return {"status_code": 0, "error": type(exc).__name__, "message": str(exc)}
    error = _error_info_fields(_envelope_error(exc.detail)) or {
        "error": "http_error",
        "message": "",
        "details": {},
        "recoverable": False,
    }
    return {"status_code": int(exc.status_code), **error}


def _as_mapping(value: Any) -> Mapping[str, Any] | None:
    """Read a Pydantic model or a plain mapping through one shape."""

    dump = getattr(value, "model_dump", None)
    if callable(dump):
        value = dump(exclude_none=True)
    return value if isinstance(value, Mapping) else None


def _envelope_error(detail: Any) -> Any:
    """Pull the ``error`` member out of an ``ErrorEnvelope`` in either carrier."""

    envelope = _as_mapping(detail)
    return None if envelope is None else envelope.get("error")


def _error_info_fields(error: Any) -> dict[str, Any] | None:
    """Project one ``ErrorInfo`` (model or mapping) onto the cause's field set."""

    fields = _as_mapping(error)
    if fields is None:
        return None
    typed = str(fields.get("error") or "").strip()
    if not typed:
        return None
    return {
        "error": typed,
        "message": str(fields.get("message") or ""),
        "details": dict(fields.get("details") or {}),
        "recoverable": bool(fields.get("recoverable", False)),
    }


def _is_terminal_cause(cause: Mapping[str, Any]) -> bool:
    """A 4xx cause will not fix itself; re-driving it forever is a silent freeze."""

    status = int(cause.get("status_code") or 0)
    return 400 <= status < 500


def _mark_head_blocked(app: Any, session_id: str, head: Any, cause: Mapping[str, Any]) -> None:
    """Emit the distinct terminal reason naming the row the client must edit.

    Nothing is deleted: the queued row stays durable, listed and editable. What
    changes is the story the client is told -- the head will NOT recover on its
    own, and the queue behind it is frozen until this row is edited or removed.
    """

    from clio_agent.gact.events import Event  # noqa: PLC0415

    logger.warning(
        "queued-message head blocked reason=queue_head_blocked session=%s message=%s cause=%s",
        session_id,
        head.id,
        cause.get("error"),
    )
    _blocked_heads(app)[session_id] = {
        "queued_message_id": head.id,
        "revision": head.revision,
        "cause": dict(cause),
    }
    app.state.bus.publish(
        Event(
            type="queued_message.head_blocked",
            session_id=session_id,
            payload={
                "queued_message_id": head.id,
                "reason": "queue_head_blocked",
                "cause": dict(cause),
                "recoverable": False,
                "blocks_queue": True,
                "recovery_actions": ["edit_queued_message", "delete_queued_message"],
            },
        )
    )


def _publish_promotion_failure(
    app: Any,
    session_id: str,
    message_id: str,
    error: str,
    *,
    cause: Mapping[str, Any],
    terminal: bool,
) -> None:
    """Emit the typed promotion failure. The row stays durable either way.

    ``retry_on`` names the concrete events that re-drive a RECOVERABLE failure. A
    terminal (4xx) cause carries no ``retry_on`` at all, because promising a
    retry that can only fail again is exactly the head-of-line freeze this
    reports.
    """

    from clio_agent.gact.events import Event  # noqa: PLC0415

    payload: dict[str, Any] = {
        "queued_message_id": message_id,
        "error": error,
        "cause": dict(cause),
        "recoverable": not terminal,
    }
    if terminal:
        payload["blocks_queue"] = True
        payload["recovery_actions"] = ["edit_queued_message", "delete_queued_message"]
    else:
        payload["retry_on"] = ["session_idle", "queue_mutation", "manual_promote"]
    app.state.bus.publish(
        Event(
            type="queued_message.promotion_failed",
            session_id=session_id,
            payload=payload,
        )
    )


def resource_capabilities(app: Any) -> dict[str, Any]:
    """Report the workspace-resource service's live limits and converter registry.

    A client must know the upload ceiling BEFORE it starts a resumable upload,
    and which converters are configured before it expects a structured view.
    Both are read off the stores this module built rather than restated, so the
    advertised contract cannot drift from what the service actually enforces.
    """

    store = getattr(app.state, "resource_store", None)
    if store is None:
        return {}
    factory = getattr(app.state, "resource_converter_factory", None)
    # A quarantined index is a REAL capability statement: the service is up but
    # its history is gone, and a client that sees an empty resource list is
    # entitled to know why rather than concluding nothing was ever uploaded.
    degradations = [
        row
        for row in (
            getattr(store, "load_degradation", None),
            getattr(getattr(app.state, "resource_delivery_store", None), "load_degradation", None),
        )
        if row
    ]
    return {
        "enabled": True,
        "max_bytes": int(store.max_resource_bytes),
        "converters": factory.capabilities() if factory is not None else [],
        "degradations": degradations,
    }


def delete_workspace_resources(app: Any, workspace_id: str) -> None:
    """Delete workspace-owned resource bytes and provider-delivery records."""

    for store_name in ("resource_store", "resource_delivery_store"):
        store = getattr(app.state, store_name, None)
        if store is not None:
            store.delete_workspace(workspace_id)
