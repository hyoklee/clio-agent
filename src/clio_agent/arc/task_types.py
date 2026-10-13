"""Shared task and session-mail records, without execution or delivery policy."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

TaskKind = Literal["Shell", "Download", "Indexing", "MCP", "Session", "Subagent", "Question"]
CoordinationRight = Literal["read", "observe", "message", "control"]
MailKind = Literal["human", "peer", "task_result", "attention", "question_answer", "control"]


class TaskRecord(BaseModel):
    """Immutable validated data written through Core's confirmed writer."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class CoreReference(TaskRecord):
    """Address and integrity of content held once in the Core hierarchy."""

    session_id: str
    scope: str
    content_id: str
    sha256: str


class TaskOwner(TaskRecord):
    """Original human, stable session and finite assignment owning accepted work."""

    human_id: str
    session_id: str
    assignment_id: str
    parent_handle: str | None = None


class BackendReference(TaskRecord):
    """Complete native identity; transport and placement are independent attributes."""

    owner: Literal["native", "external_mcp", "conversation", "question"]
    server: str = ""
    auth_scope: str = ""
    session: str = ""
    task_id: str = ""
    queue: str = ""
    execution_key: str = ""
    transport: str = ""
    placement: str = "local"


class TaskProgress(TaskRecord):
    """Owner-reported progress, with no invented percentage or terminal inference."""

    message: str = ""
    completed: float | None = Field(default=None, ge=0)
    total: float | None = Field(default=None, ge=0)
    unit: str = ""
    output: CoreReference | None = None


class TaskSnapshot(TaskRecord):
    """One passive common view; the execution owner supplies status and settlement."""

    handle: str
    kind: TaskKind
    owner: TaskOwner
    description: str | None = None
    description_missing: bool = True
    label: str
    invocation_id: str
    tool: str
    created_at: str
    updated_at: str
    backend: BackendReference | None = None
    raw_status: str = ""
    status: str = "accepted"
    activity: str = ""
    progress: TaskProgress = Field(default_factory=TaskProgress)
    supported_actions: tuple[str, ...] = ()
    cancellation_requested_at: str | None = None
    connection_freshness: str = "unknown"
    settlement: str = "unknown"
    recording: Literal["confirmed", "unconfirmed"] = "confirmed"
    terminal_at: str | None = None
    result: CoreReference | None = None
    details: CoreReference | None = None

    @model_validator(mode="after")
    def validate_description_presence(self) -> TaskSnapshot:
        """Missing historical descriptions stay explicit rather than invented."""
        if self.description_missing != (self.description is None):
            raise ValueError("Description presence and missing-description marker disagree")
        return self


class SubmissionContext(TaskRecord):
    """Trusted pre-submission context referenced explicitly by an owned worker."""

    reference: str
    handle: str
    owner: TaskOwner
    invocation_id: str
    tool: str
    argument_digest: str
    arguments: dict[str, JsonValue]
    workspace: str
    permissions: dict[str, JsonValue]
    confinement: dict[str, JsonValue]
    attribution: dict[str, JsonValue]
    execution_limits: dict[str, JsonValue]


class NativeAttempt(TaskRecord):
    """An observed execution incarnation, distinct from Docket's retry counter."""

    handle: str
    incarnation: str
    backend: BackendReference
    leg: int = Field(ge=1)
    started_at: str
    cleanup_receipt: CoreReference | None = None


class MailItem(TaskRecord):
    """An attributed session input; acceptance does not acknowledge delivery."""

    id: str
    recipient_session: str
    sender_session: str | None = None
    sender_human: str | None = None
    kind: MailKind
    content: CoreReference
    created_at: str
    handle: str | None = None
    episode: str | None = None


class ContextBoundary(TaskRecord):
    """Fixed existing Core context checkpoint used to reconstruct a model input."""

    session_id: str
    scope: str
    logical_time: int = Field(ge=0)


class RecipientInput(TaskRecord):
    """The sole notification acknowledgement, confirmed before model execution."""

    id: str
    session_id: str
    assignment_id: str
    iteration_id: str
    boundary: ContextBoundary
    notification_ids: tuple[str, ...]
    content: tuple[CoreReference, ...]
    committed_at: str
    tool_observation: CoreReference | None = None


class CoordinationGrant(TaskRecord):
    """Human/configuration-created relationship; model intent conveys no rights."""

    id: str
    granting_human: str
    recipient_session: str
    target_session: str
    rights: tuple[CoordinationRight, ...]
    created_at: str
    target_handle: str | None = None
    revoked_at: str | None = None


class QuestionOption(TaskRecord):
    """One displayed option and its exact answer value."""

    label: str
    value: str
    description: str = ""


class QuestionDefinition(TaskRecord):
    """Question content; lifecycle exists only in its common TaskSnapshot."""

    prompt: str
    kind: Literal["freeform", "choice", "confirmation", "multi_choice"] = "freeform"
    options: tuple[QuestionOption, ...] = ()
    allow_freeform: bool = True
    requested_schema: dict[str, JsonValue] | None = None
    expires_at: str | None = None
    source: str = "ask_user"
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class QuestionReply(TaskRecord):
    """Stored answer, with the existing composer attachment/reference payload."""

    answer: str = ""
    selected_options: tuple[str, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    parts: tuple[dict[str, JsonValue], ...] = ()
