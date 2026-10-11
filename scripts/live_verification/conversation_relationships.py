"""Create and verify a public-safe conversation family with real Codex/Luna turns."""

from __future__ import annotations

import argparse
from pathlib import Path

from conversation_controls import Acceptance


def main() -> int:
    """Retain real requests, responses, fork checkpoints and independent continuations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default="http://127.0.0.1:17963")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    runner = Acceptance(args.endpoint, args.out)
    runner.call(
        "PUT", "/v1/providers/lm", {"provider": "codex", "model": "gpt-6-luna", "api_base": ""}
    )
    ready = runner.call("GET", "/v1/providers/lm/wait?timeout=20")
    runner.check("real Luna provider ready", ready.get("state") == "ready", ready.get("state"))
    runner.workspace = runner.call(
        "POST",
        "/v1/workspaces",
        {"name": "Calibration alternatives", "root_path": str(args.workspace)},
        status=201,
    )["id"]
    root = runner.call(
        "POST",
        "/v1/sessions",
        {
            "title": "Calibration baseline",
            "workspace_id": runner.workspace,
            "approval_mode": "bypass",
            "metadata": {"effort": "low"},
        },
    )["id"]
    runner.sessions["baseline"] = root
    baseline = runner.turn(
        root,
        "This is fictional calibration data for a public CLIO walkthrough: readings 10, 12 and 14. Calculate their mean. Use create_artifact to author calibration-baseline.md, a short Markdown record of the readings and calculation. Use content, kind='other', and pdf_preview=false. Do not use shell or environment tools. End the visible answer with Mean: 12.",
        "baseline and real artifact",
        12,
    )
    branch = runner.fork(root, "Offset comparison", baseline["id"])
    branch_before = runner.messages(branch)
    runner.turn(
        branch,
        "For this independent branch keep all original readings, add an offset of +2 to each, and remember that method. Use create_artifact to author calibration-offset.md from calibration-baseline.md, declaring used=['calibration-baseline.md'], kind='other', pdf_preview=false. Keep the visible answer to two sentences; do not use shell tools.",
        "offset alternative",
        14,
    )
    nested = runner.fork(branch, "Offset sensitivity")
    runner.turn(
        nested,
        "Increase our offset by another +3, retaining all original readings. Remember the resulting +5 offset. Two sentences, no tools.",
        "nested alternative",
        17,
    )
    filtered = runner.fork(root, "Flagged reading comparison", baseline["id"])
    runner.turn(
        filtered,
        "Exclude reading 14 as a fictional flagged measurement. Keep the other two unchanged. Remember this method. Two sentences without tools.",
        "filtered alternative",
        11,
    )
    runner.check("parent remains baseline", len(runner.messages(root)) == 2, root)
    origin = runner.call("GET", f"/v1/sessions/{branch}")["metadata"]["fork_origin"]
    runner.check(
        "saved message checkpoint",
        origin["message_id"] == baseline["id"] and origin["message_count"] == len(branch_before),
        origin,
    )
    runner.call(
        "POST", f"/v1/sessions/{root}/rewind", {"message_id": runner.messages(root)[0]["id"]}
    )
    runner.check(
        "checkpoint survives parent rewind",
        runner.call("GET", f"/v1/sessions/{branch}")["metadata"]["fork_origin"] == origin,
        origin,
    )
    runner.turn(
        root,
        "For the main conversation retain our original readings without an offset. State their mean in two short sentences without tools.",
        "parent after rewind",
        12,
    )
    runner.turn(
        branch,
        "Recall this branch's current calibration method and mean. Two sentences, no tools.",
        "branch retains independent context",
        14,
    )
    runner.save(
        "acceptance-state",
        {
            "workspace": runner.workspace,
            "baseline_message": baseline["id"],
            "sessions": runner.sessions,
            "origin": origin,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
