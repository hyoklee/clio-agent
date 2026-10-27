"""Copy a conversation's transcript and context files into another session.

One mechanism serves every copy: a person's fork of a conversation, a side
session, and an agent's fork of itself. The copy is a deep copy of the stored
messages through an optional message, plus the session's context files. An
agent's fork also carries the turn it forks from, which is not stored until the
turn ends: the open turn's parts through its last finished tool result, without a
call still in flight (the ``fork`` call among them). The copied session's model
context is then restored from this transcript on its first turn
(:func:`~clio_agent.gact.agents.context_identity.restore_context`).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from clio_agent.gact.types import Message


def stored_messages(app: Any, src: str, at: str = "") -> list[Message]:
    """``src``'s stored messages, through ``at`` when it names one of them."""

    messages = list(app.state.messages.get(src, []))
    if at and any(message.id == at for message in messages):
        messages = messages[: next(i for i, m in enumerate(messages) if m.id == at) + 1]
    return messages


def open_turn_message(app: Any, src: str, dst: str) -> Message | None:
    """The finished part of ``src``'s open turn, as an assistant message of ``dst``.

    Parts are kept through the last ``tool_result``; a ``tool_call`` with no result
    yet is left out. ``None`` when ``src`` has no open turn or nothing finished.
    """

    from clio_agent.gact.tool_observer import _session_turn_transcript  # noqa: PLC0415

    transcript = _session_turn_transcript(app, src)
    parts = list(transcript.snapshot()) if transcript is not None else []
    last = max((i for i, part in enumerate(parts) if part.type == "tool_result"), default=-1)
    finished = {part.call_id for part in parts[: last + 1] if part.type == "tool_result"}
    kept = [
        part.model_copy(deep=True)
        for part in parts[: last + 1]
        if part.type != "tool_call" or part.call_id in finished
    ]
    if not kept:
        return None
    now = datetime.now(timezone.utc).isoformat()
    return Message(
        id="msg_" + uuid4().hex[:12],
        turn_id=str(getattr(transcript, "turn_id", "") or ""),
        session_id=dst,
        role="assistant",
        created_at=now,
        updated_at=now,
        parts=kept,
    )


def copy_conversation(
    app: Any, src: str, dst: str, at: str = "", *, open_turn: bool = False
) -> int:
    """Deep-copy ``src``'s messages (through ``at``) and context files into ``dst``.

    ``open_turn`` adds the finished part of ``src``'s open turn (an agent forking
    itself mid-turn). Returns the number of messages copied. Runs off the loop.
    """

    copied = [
        m.model_copy(deep=True, update={"session_id": dst}) for m in stored_messages(app, src, at)
    ]
    if open_turn and (current := open_turn_message(app, src, dst)) is not None:
        copied.append(current)
    app.state.gact_deps.replace_session_messages(app, dst, copied)
    if source_context_files := app.state.context_files.get(src, {}):
        app.state.context_files[dst] = {k: dict(row) for k, row in source_context_files.items()}
    return len(copied)


__all__ = ["copy_conversation", "create_branch", "open_turn_message", "stored_messages"]


#: Configuration a branch copies from its conversation: never task ownership or pending work.
BRANCH_METADATA_KEYS = frozenset(
    {
        "agent_ref",
        "agent_delta",
        "agent_resolution",
        "effort",
        "effort_source",
        "thinking_level",
        "branch",
        "git_branch",
        "memory_snapshot",  # memory as of the fork point (MD16)
        "memory_off",
    }
)


def create_branch(
    app: Any,
    source: Any,
    *,
    title: str = "",
    at: str = "",
    open_turn: bool = False,
    origin: dict[str, Any] | None = None,
) -> Any:
    """A new conversation branch of ``source``: its configuration and its transcript
    through ``at`` (and, for an agent forking mid-turn, the open turn's finished part).

    ``origin`` adds to the branch's ``fork_origin`` record (an agent fork names its
    author and the call that made it). Runs off the loop.
    """

    from clio_agent.gact.conversation_origin import FORK_ORIGIN_KEY  # noqa: PLC0415
    from clio_agent.gact.message_marks import saved_message_marks  # noqa: PLC0415
    from clio_agent.gact.runtime.permission_policies import (  # noqa: PLC0415
        inherit_child_session_policies,
    )

    metadata = {key: value for key, value in source.metadata.items() if key in BRANCH_METADATA_KEYS}
    metadata["session_kind"] = "branch"
    branch = app.state.sessions.create(
        workspace_id=source.workspace_id,
        title=title or f"{source.title} (fork)",
        parent_session_id=source.id,
        model=dict(source.model),
        agent={key: value for key, value in source.agent.items() if key != "mode"},
        metadata=metadata,
        mode=source.mode,
        edit_mode=source.edit_mode,
        routing_mode=source.routing_mode,
        approval_mode=source.approval_mode,
        approval_profile=source.approval_profile,
    )
    inherit_child_session_policies(app, source.id, branch.id)
    copied = copy_conversation(app, source.id, branch.id, at, open_turn=open_turn)
    messages = app.state.messages.get(branch.id, [])
    app.state.sessions.update(
        branch.id,
        message_count=copied,
        metadata_patch={
            FORK_ORIGIN_KEY: {
                "session_id": source.id,
                "message_id": messages[-1].id if messages else "",
                "message_count": copied,
                "title": source.title,
                "created_at": branch.created_at,
                **(origin or {}),
            },
            "message_marks": saved_message_marks(
                source.metadata, {message.id for message in messages}
            ),
        },
    )
    return app.state.sessions.get(branch.id)
