"""Retain and register small observed inputs without treating them as outputs."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from clio_agent.gact.artifacts.designation import kind_for_path
from clio_agent.gact.artifacts.minting import mint_artifact_outcome
from clio_agent.gact.artifacts.records import Custody, IdentityEvidence, Mechanism
from clio_agent.gact.artifacts.registry import MintOutcome
from clio_agent.gact.artifacts.storage import ingest_artifact_identity

if TYPE_CHECKING:
    from fastapi import FastAPI


def mint_consumed_input(
    app: FastAPI,
    sid: str,
    *,
    path: str,
    workspace_root: Path,
    workspace_id: str,
    evidence: IdentityEvidence,
    tool_name: str,
    call_id: str,
    turn_id: str,
    trace_id: str,
    granted_input: bool,
    notes: list[dict[str, Any]],
) -> MintOutcome | None:
    """Preserve the consumed version before subsequent workspace edits.

    Use the selected store's bounded ingestion and custody. A failed copy keeps
    explicit reference-only evidence; a concurrent change never mints a version
    claiming that the newly copied bytes were the previously observed input.
    """
    retained = None
    try:
        retained = ingest_artifact_identity(app, path, workspace_root=workspace_root)
    except OSError as exc:
        notes.append({"reason": "used_input_not_retained", "path": path, "error": str(exc)})
    if retained is not None and retained.evidence.sha256 != evidence.sha256:
        notes.append({"reason": "used_input_changed_during_registration", "path": path})
        return None
    return mint_artifact_outcome(
        app,
        sid,
        name=Path(path).name,
        workspace_id=workspace_id,
        evidence=evidence,
        kind=kind_for_path(path),
        mechanism=Mechanism.TOOL_SCHEMA,
        custody=retained.custody if retained is not None else Custody.WORKSPACE_REFERENCED,
        ingested=retained,
        producing=False,
        path=path,
        turn_id=turn_id,
        trace_id=trace_id,
        # Preserve consuming-call identity, without asserting a generated output.
        producer={
            "designation": "used-granted-file" if granted_input else "used-script",
            "session_id": sid,
            "tool": tool_name,
            "call_id": call_id,
            "turn_id": turn_id,
        },
    )
