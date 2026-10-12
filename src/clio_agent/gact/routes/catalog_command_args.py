"""Pure slash-command argument rendering and validation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException

from clio_agent.gact.catalog import _truthy_command_field
from clio_agent.gact.types import ErrorEnvelope, ErrorInfo


def _render_command_prompt(
    command_meta: Mapping[str, Any],
    *,
    user_input: str,
    args: Any,
    cmd_id: str,
    agent_id: str,
) -> str:
    prompt_template = str(command_meta.get("prompt_template") or "")
    if not prompt_template:
        return user_input or str(command_meta.get("description") or cmd_id)
    rendered = (
        prompt_template.replace("{{input}}", user_input)
        .replace("{{args}}", user_input)
        .replace("$ARGUMENTS", user_input)
        .replace("{{command}}", cmd_id)
        .replace("{{agent_id}}", agent_id)
    )
    if isinstance(args, Mapping):
        for key, value in args.items():
            rendered = rendered.replace(f"{{{{args.{key}}}}}", str(value))
    return rendered


def _command_required_argument_names(command_meta: Mapping[str, Any]) -> list[str]:
    specs = command_meta.get("arguments") or []
    if isinstance(specs, str):
        return [specs] if specs.strip() else []
    if not isinstance(specs, list):
        return []
    required: list[str] = []
    for spec in specs:
        if isinstance(spec, str) and spec.strip():
            required.append(spec.strip())
        elif isinstance(spec, Mapping) and _truthy_command_field(
            spec.get("required"),
            False,
        ):
            name = str(spec.get("name") or spec.get("id") or "").strip()
            if name:
                required.append(name)
    return required


def _validate_command_arguments(
    command_meta: Mapping[str, Any],
    *,
    args: Any,
    user_input: str,
    cmd_id: str,
) -> None:
    required = _command_required_argument_names(command_meta)
    if not required:
        return
    if not isinstance(args, Mapping):
        if user_input:
            return
        missing = required
    else:
        missing = [name for name in required if args.get(name) in (None, "")]
    if not missing:
        return
    raise HTTPException(
        status_code=422,
        detail=ErrorEnvelope(
            error=ErrorInfo(
                error="invalid_arguments",
                message=f"command {cmd_id} is missing required arguments",
                details={
                    "command": cmd_id,
                    "missing": missing,
                    "argument_hint": command_meta.get("argument_hint", ""),
                },
                recoverable=True,
            )
        ).model_dump(exclude_none=True),
    )
