"""Question routes delegate to the single native/external interaction owner."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException

from clio_agent.gact.events import Event
from clio_agent.gact.parts import Part
from clio_agent.gact.permission_delivery import attended_session_id
from clio_agent.gact.routes.session_question_helpers import (
    normalize_question_options,
    question_already_resolved,
    question_not_found,
)
from clio_agent.gact.runtime.globals import _new_question_id
from clio_agent.gact.types import (
    AnswerUserQuestionRequest,
    CreateUserQuestionRequest,
    ErrorEnvelope,
    ErrorInfo,
    UserQuestion,
)
