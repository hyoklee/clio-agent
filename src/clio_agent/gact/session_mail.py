"""One session mailbox over confirmed Core history and recipient-input commitments."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from uuid import uuid4

from clio_agent import conf
from clio_agent.arc.task_types import ContextBoundary, CoreReference, MailItem, RecipientInput
from clio_agent.gact.native_work import now
from clio_agent.gact.task_access import TaskAccess, TaskCaller
from clio_agent.gact.task_history import MailboxFull, TaskHistory
from clio_agent.gact.task_publication import task_owner_recipient

Eligibility = Callable[[str, MailItem], bool]


class MailText(str):
    """A context injection carrying stable Core notification identities."""

    notification_ids: tuple[str, ...]

    def __new__(cls, value: str, identities: tuple[str, ...]) -> MailText:
        instance = super().__new__(cls, value)
        instance.notification_ids = identities
        return instance


@dataclass(frozen=True)
class StagedInput:
    """Unacknowledged selection; interruption or veto leaves every item Core-pending."""

    items: tuple[MailItem, ...]
    injections: tuple[tuple[str, MailText], ...]
    collected: tuple[str, ...] = ()


class SessionMail:
    """Compose bounded model input without a lossy inbox or competing delivery guard."""

    def __init__(
        self,
        history: TaskHistory,
        eligible: Eligibility,
        committed: Callable[[StagedInput], None] | None = None,
    ) -> None:
        self.history, self.eligible = history, eligible
        self.committed = committed

    def stage(self, caller: TaskCaller, *, collected: tuple[str, ...] = ()) -> StagedInput:
        """Read eligible arrivals in accepted order; no query/staging operation consumes them."""
        with self.history._lock:
            access = TaskAccess(self.history, caller)
            items: list[MailItem] = []
            injections: list[tuple[str, MailText]] = []
            budget = conf.resolve(
                "limits.model_tool_result_chars",
                env="CLIO_MODEL_TOOL_RESULT_CHARS",
                default=12000,
                cast=conf.as_int,
            )
            used = 0
            for item in self.history.pending_mail(caller.session_id):
                if item.delivery != "eligible" or not self.eligible(caller.session_id, item):
                    continue
                if not self._authorized(item, access):
                    continue
                if item.handle is not None and item.kind in {
                    "task_result",
                    "attention",
                    "question_answer",
                }:
                    task = self.history.task_snapshot(item.handle)
                    if task is None or "read" not in access.rights(task):
                        continue
                if item.id in collected:
                    items.append(item)
                    continue
                value = self.history.read_content(item.content)
                rendered = (
                    value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
                )
                sender = (
                    f"Human {item.sender_human}"
                    if item.sender_human
                    else f"Agent session {item.sender_session}"
                    if item.sender_session
                    else "CLIO"
                )
                task_label = ""
                if item.handle is not None and item.kind in {
                    "task_result",
                    "attention",
                    "question_answer",
                }:
                    task = self.history.task_snapshot(item.handle)
                    if task is not None:
                        task_label = f"; {task.kind} {task.handle}: {task.status}"
                        if (
                            task.status in {"failed", "task_state_uncertain"}
                            and task.progress.message
                        ):
                            task_label += f" ({task.progress.message})"
                text = f"[{sender}; {item.kind}{task_label}; notification {item.id}]\n{rendered}"
                if budget > 0 and used + len(text) > budget:
                    if injections:
                        break
                    text = (
                        text[:budget]
                        + f"\n[Full content retained at {item.content.scope}; task {item.handle or ''}.]"
                    )
                source = "steer" if item.kind in {"human", "composer"} else item.kind
                injections.append((source, MailText(text, (item.id,))))
                items.append(item)
                used += len(text)
            return StagedInput(tuple(items), tuple(injections), collected)

    def commit(
        self,
        caller: TaskCaller,
        staged: StagedInput,
        *,
        assignment_id: str,
        iteration_id: str,
        boundary: ContextBoundary,
        tool_observation: CoreReference | None = None,
        rendered_content: tuple[CoreReference, ...] = (),
        turn_id: str = "",
    ) -> RecipientInput:
        """Recheck permission/eligibility, then confirm the sole delivery acknowledgement."""
        with self.history._lock:
            access = TaskAccess(self.history, caller)
            pending = {item.id: item for item in self.history.pending_mail(caller.session_id)}
            for item in staged.items:
                if pending.get(item.id) != item:
                    raise ValueError("Staged input changed; restage before model execution")
                explicit_collection = (
                    tool_observation is not None
                    and item.id in staged.collected
                    and item.kind in {"task_result", "question_answer"}
                )
                if not explicit_collection and (
                    item.delivery != "eligible" or not self.eligible(caller.session_id, item)
                ):
                    raise ValueError("Staged input is gated; retain it pending")
                if not self._authorized(item, access):
                    raise ValueError("Staged input authorization changed; retain it pending")
                if item.handle is not None and item.kind in {
                    "task_result",
                    "attention",
                    "question_answer",
                }:
                    access.require(item.handle, "read")
            record = RecipientInput(
                id=assignment_id + ":" + iteration_id,
                session_id=caller.session_id,
                assignment_id=assignment_id,
                iteration_id=iteration_id,
                boundary=boundary,
                notification_ids=tuple(item.id for item in staged.items),
                content=tuple(item.content for item in staged.items),
                committed_at=now(),
                tool_observation=tool_observation,
                rendered_content=rendered_content,
                turn_id=turn_id,
                human_input=any(item.kind in {"human", "composer"} for item in staged.items),
            )
            confirmed = self.history.record_input(record)
        if self.committed is not None:
            self.committed(staged)
        return confirmed

    def collection(self, caller: TaskCaller, identities: tuple[str, ...]) -> StagedInput:
        """Select only notices represented by a persisted explicit tool observation."""
        with self.history._lock:
            access = TaskAccess(self.history, caller)
            items = tuple(
                item
                for item in self.history.pending_mail(caller.session_id)
                if item.id in identities and self._authorized(item, access)
            )
            return StagedInput(items, (), tuple(item.id for item in items))

    def _authorized(self, item: MailItem, recipient: TaskAccess) -> bool:
        if item.kind == "peer":
            if item.sender_session is None:
                return False
            assignment = self.history.latest_assignment(item.sender_session)
            sender = TaskAccess(
                self.history,
                TaskCaller(
                    item.sender_session, assignment.owner.human_id if assignment is not None else ""
                ),
            )
            if item.handle is None:
                return sender.session_message_right(item.recipient_session)
            task = self.history.task_snapshot(item.handle)
            return (
                task is not None
                and "message" in sender.rights(task)
                and (task.terminal_at is None or sender.stable_message_right(task))
            )
        if item.kind in {"task_result", "attention", "question_answer"} and item.handle is not None:
            task = self.history.task_snapshot(item.handle)
            if task is None or "read" not in recipient.rights(task):
                return False
            if task_owner_recipient(self.history, task) == item.recipient_session:
                return True
            if "observe" not in recipient.rights(task):
                return False
            return any(
                subscription.enabled and subscription.recipient_session == item.recipient_session
                for subscription in self.history.subscriptions(task.handle)
            )
        return True

    def peer(
        self,
        caller: TaskCaller,
        target: str,
        message: str,
        *,
        invocation_id: str = "",
        reply_to: str | None = None,
    ) -> MailItem:
        """Accept an attributed message to an exact authorized stable session."""
        if not message.strip():
            raise ValueError("Peer message cannot be empty")
        with self.history._lock:
            access = TaskAccess(self.history, caller)
            resolved = self.history.resolve_handle(target)
            if resolved is not None:
                task = access.require(resolved, "message")
                if task.terminal_at is not None and not access.stable_message_right(task):
                    raise ValueError(
                        "Historical assignment grant cannot address a successor session"
                    )
                recipient, handle = task.owner.session_id, task.handle
            else:
                if not access.session_message_right(target):
                    raise ValueError("Session is unavailable for messaging")
                recipient, handle = target, None
            value = {"text": message, "reply_to": reply_to}
            identity = (
                "mail_"
                + hashlib.sha256((caller.session_id + "\0" + invocation_id).encode()).hexdigest()
                if invocation_id
                else "mail_" + uuid4().hex
            )
            previous = self.history._mail.get(recipient, {}).get(identity)
            if previous is not None:
                if (
                    previous.sender_session != caller.session_id
                    or previous.handle != handle
                    or self.history.read_content(previous.content) != value
                ):
                    raise ValueError(
                        "Message invocation identity was reused with different content"
                    )
                return previous
            if reply_to is not None:
                original = self.history._mail.get(caller.session_id, {}).get(
                    reply_to
                ) or self.history._mail.get(recipient, {}).get(reply_to)
                if original is None or {original.sender_session, original.recipient_session} != {
                    caller.session_id,
                    recipient,
                }:
                    raise ValueError("Reply target is unavailable for these sessions")
            limit = conf.resolve(
                "gact.mailbox.max_pending_messages",
                env="CLIO_MAILBOX_MAX_PENDING_MESSAGES",
                default=0,
                cast=conf.as_int,
            )
            if (
                limit > 0
                and sum(item.kind == "peer" for item in self.history.pending_mail(recipient))
                >= limit
            ):
                raise MailboxFull("Undelivered peer-message capacity reached; retry later")
            content = self.history.write_content(recipient, value)
            return self.history.record_mail(
                MailItem(
                    id=identity,
                    recipient_session=recipient,
                    sender_session=caller.session_id,
                    kind="peer",
                    content=content,
                    created_at=now(),
                    handle=handle,
                ),
                max_pending_messages=limit,
            )
