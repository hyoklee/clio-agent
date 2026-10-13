"""Task-reference evidence forwarding on spawn (#1306 review round, finding 1).

The digest half (``agent_task_output_digest.py``) keeps the PARENT lean when it
collects an oversize completed child's output. That alone forces the exact flow
#1306 named as motivating (a coordinator sending assembled researcher evidence
through an independent critic) back through the parent: it would have to
``get_agent_task_output`` every researcher and re-inline the sum right back into
its own context -- the SAME bloat, one hop later.

This module is the other half: a typed ``input_task_ids`` reference on
``spawn_agent_task`` / ``spawn_agents_parallel``'s per-spawn entries. The parent
never touches the text -- it passes ids; the runtime resolves each referenced
task's FULL stored output (the identical ``spawn_runtime._resolve_verbatim_output``
path ``wait_agent_tasks`` and ``get_agent_task_output`` already use) and appends it,
clearly labeled, to the CHILD's own task briefing. The material lands in the
child's OWN context, never the parent's -- which is the point: a critic gets full
researcher evidence without the coordinator ever holding it.

Validation is a reality check, not a decision: an id must belong to the SPAWNING
session's own task registry scope (it spawned that task) and have reached a
terminal status, or the spawn is refused typed (no child created) rather than
silently starting a critic with a missing/foreign/incomplete reference. Nothing
here decides what the child does with the evidence -- forwarding it is the whole
mechanism.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# The two structural tokens an evidence block's header/footer use. The output
# they wrap is UNTRUSTED (the motivating case is web content a researcher child
# fetched) -- see _sanitize_evidence_output (#1306 final review round, finding
# B1) for why matching text inside it must never reach the child briefing raw.
_EVIDENCE_DELIMITER_RE = re.compile(r"(?m)^-{2,}\s*(Evidence from|end evidence)\b")


def _sanitize_evidence_output(output: str) -> str:
    """Neutralize the evidence-block delimiter tokens inside untrusted output.

    Mirrors the repo's decided precedent for the SAME class of problem
    (``gact/enrichment.py``'s ``_sanitize_excerpt``, #948 S6 adversarial-review
    [5]): a child's stored output is untrusted content that may reflect a
    poisoned document/page/tool result. Embedded raw between
    ``--- Evidence from ... ---`` / ``--- end evidence (...) ---`` delimiters, a
    poisoned answer could emit its OWN ``--- end evidence (task_r1) ---`` line
    followed by a forged ``--- Evidence from <trusted-agent> ---`` header,
    attributing fabricated material to a sibling task inside the SAME briefing.
    This replaces the two STRUCTURAL prefixes the referenced task's own output
    must never control (a run of 2+ dashes immediately followed by "Evidence
    from" or "end evidence" at the start of a line) with a single dash, so
    embedded text can never forge a new frame boundary. Content is otherwise
    preserved verbatim -- this is a delimiter fix, not a content redaction.
    """

    return _EVIDENCE_DELIMITER_RE.sub(r"- \1", output)


def _evidence_block(task: Any, output: str, fallback_reason: str) -> str:
    """One clearly labeled evidence block: which child, which agent, which task.

    ``fallback_reason`` (#1306 final review round, finding N1) is
    ``_resolve_verbatim_output``'s typed degradation marker
    (``output_fallback_reason``) when the child's message is gone and ``output``
    is only the bounded durable excerpt, not the true full text -- folded into
    the header itself (``PARTIAL: <reason>``) so the child sees the material is
    incomplete instead of silently receiving a 2000-char stub labeled as full
    evidence. Empty when the resolve was clean.
    """

    agent_id = task.agent_ref.get("expert_id", "")
    header = (
        f"--- Evidence from {agent_id} (task {task.task_id}, child session {task.child_session_id}"
    )
    if fallback_reason:
        header += f", PARTIAL: {fallback_reason}"
    header += ") ---"
    return f"{header}\n{_sanitize_evidence_output(output)}\n--- end evidence ({task.task_id}) ---"
