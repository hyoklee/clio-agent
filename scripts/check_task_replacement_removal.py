"""Reject reintroduction of the task owners removed by the R2 replacement.

Run directly with uv; this guard does not import the deliberately broken product.
Historical data may retain old field names, but may not import an execution owner.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REMOVED_MODULES = frozenset(
    [
        "clio_agent.gact.agent_tasks",
        "clio_agent.gact.agent_task_admission",
        "clio_agent.gact.agent_task_recovery",
        "clio_agent.gact.agent_task_notifications",
        "clio_agent.gact.assignment_history",
        "clio_agent.gact.agent_mailbox",
        "clio_agent.gact.async_user_question",
        "clio_agent.gact.child_forward",
        "clio_agent.gact.core_task_journal",
        "clio_agent.gact.human_task_intervention",
        "clio_agent.gact.loop_inbox",
        "clio_agent.gact.mcp_task_events",
        "clio_agent.gact.mcp_task_store",
        "clio_agent.gact.question_tasks",
        "clio_agent.gact.session_run_tasks",
        "clio_agent.gact.subagent_lifecycle",
        "clio_agent.gact.subagent_restart",
        "clio_agent.gact.task_backend_identity",
        "clio_agent.gact.task_completion_wake",
        "clio_agent.gact.task_context_frame",
        "clio_agent.gact.task_controls",
        "clio_agent.gact.task_delivery",
        "clio_agent.gact.task_fold",
        "clio_agent.gact.task_input_owner",
        "clio_agent.gact.task_input_questions",
        "clio_agent.gact.task_mcp_owner",
        "clio_agent.gact.task_notifications",
        "clio_agent.gact.task_permissions",
        "clio_agent.gact.task_projection",
        "clio_agent.gact.task_recovery",
        "clio_agent.gact.task_recovery_client",
        "clio_agent.gact.task_relay_owner",
        "clio_agent.gact.task_subagent_owner",
        "clio_agent.gact.task_submission_custody",
        "clio_agent.gact.task_subscriptions",
        "clio_agent.gact.task_supervisor",
        "clio_agent.gact.task_tools",
        "clio_agent.gact.turn_spawn",
        "clio_agent.gact.turn_spawn_executor",
        "clio_agent.gact.run_registry",
        "clio_agent.gact.agent_targets",
        "clio_agent.gact.agent_messaging",
        "clio_agent.gact.agent_session_messaging",
        "clio_agent.gact.agent_message_transport",
        "clio_agent.gact.relay_wiring",
        "clio_agent.gact.relay_status",
        "clio_agent.gact.relay_timeline",
        "clio_agent.gact.agents.relay_expert_invoker",
        "clio_agent.gact.agents.relay_invoker_runtime",
        "clio_agent.gact.routes.agent_tasks",
        "clio_agent.gact.routes.async_processes",
        "clio_agent.gact.routes.relay",
        "clio_agent.tools.mcp_tasks",
        "clio_agent.tools.mcp_task_records",
        "clio_agent.tools.mcp_task_lease",
        "clio_agent.tools.mcp_task_extension",
        "clio_agent.tools.mcp_wait_ladder",
        "clio_agent.tools.task_driver_lease",
        "clio_agent.tools.task_observers",
        "clio_agent.tools.task_submission",
        "clio_agent.tools.native_task_host",
        "clio_agent.tools.native_task_tool",
        "clio_agent.tools.mcp_call_progress",
        "clio_agent.tools.relay_transport",
        "clio_agent.tools.relay_factory",
        "clio_agent.tools.relay_contract",
        "clio_agent.tools.relay_console_stream",
        "clio_agent.tools.relay_console",
        "clio_agent.tools.relay_cli_runner",
        "clio_agent.tools.relay_artifact_fetch",
        "clio_agent.tools.relay_install_jobs",
        "clio_agent.tools.relay_install_surface",
        "clio_agent.gact.agent_lifecycle_tools",
        "clio_agent.gact.ask_user_tool",
        "clio_agent.gact.background_exit",
        "clio_agent.gact.goal_wait",
        "clio_agent.gact.live_handle",
        "clio_agent.gact.message_admission",
        "clio_agent.gact.user_question_ledger",
        "clio_agent.gact.user_question_resume",
        "clio_agent.gact.user_question_pause",
        "clio_agent.gact.agent_elicitation_answer_turn",
        "clio_agent.gact.agents.invoker",
        "clio_agent.gact.agents.observe_runtime",
        "clio_agent.gact.agents.spawn_placement",
        "clio_agent.gact.agents.spawn_runtime",
        "clio_agent.gact.agents.spawn_runtime_declarations",
        "clio_agent.gact.agents.skill_spawn_effect",
        "clio_agent.tools.jarvis_jobs",
        "clio_agent.tools.jarvis_result_contract",
        "clio_agent.tools.remote_mcp",
        "clio_agent.gact.routes.agent_lifecycle",
        "clio_agent.tools.servers.storage_server",
    ]
)
REMOVED_NAMES = frozenset(
    {
        "AgentTaskRegistry",
        "CoreTaskRecordStore",
        "InMemoryTaskRecordStore",
        "NativeTaskHost",
        "CoreTaskJournal",
        "TaskSupervisor",
        "TaskLease",
        "drive_task_to_terminal",
        "_poll_until_terminal",
        "drive_with_lease",
        "consume_notification",
        "install_agent_task_registry",
        "persist_agent_task",
        "seed_agent_task",
        "install_agent_task_executor",
        "shutdown_agent_task_executors",
        "agent_task_executor_for_depth",
        "install_mcp_task_event_publisher",
        "register_relay_routes",
        "register_async_process_routes",
        "configure_relay_expert_invokers",
        "refresh_relay_tool_surfaces_if_stale",
    }
)
REMOVED_STATE = frozenset(
    {"agent_task_registry", "core_task_journal", "task_supervisor", "agent_task_executors"}
)
REMOVED_CONFIG = frozenset({"agents.child_forward_deadline_s", "CLIO_CHILD_FORWARD_DEADLINE_S"})
# No unfinished branch interface has a compatibility exemption.
COMPATIBILITY_ALIASES: frozenset[str] = frozenset()


def violations(root: Path = ROOT) -> list[str]:
    """Find retired production authority, import, configuration and catalog bindings."""
    findings: list[str] = []
    for path in sorted((root / "src" / "clio_agent").rglob("*.py")):
        source = path.read_text(encoding="utf-8-sig")
        relative = path.relative_to(root).as_posix()
        try:
            tree = ast.parse(source)
        except SyntaxError as error:
            findings.append(f"{relative}:{error.lineno}: cannot audit syntax: {error.msg}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                candidates = {node.module, *(f"{node.module}.{alias.name}" for alias in node.names)}
                for module in candidates & REMOVED_MODULES:
                    findings.append(f"{relative}:{node.lineno}: removed import {module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in REMOVED_MODULES:
                        findings.append(f"{relative}:{node.lineno}: removed import {alias.name}")
            if isinstance(node, ast.Name) and node.id in REMOVED_NAMES:
                findings.append(f"{relative}:{node.lineno}: retired symbol {node.id}")
            elif isinstance(node, ast.Attribute) and node.attr in REMOVED_NAMES | REMOVED_STATE:
                findings.append(f"{relative}:{node.lineno}: retired attribute {node.attr}")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                if node.value in REMOVED_STATE | REMOVED_CONFIG | REMOVED_MODULES:
                    findings.append(f"{relative}:{node.lineno}: retired binding {node.value}")
    defaults = root / "src" / "clio_agent" / "config.defaults.yaml"
    for number, line in enumerate(defaults.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("relay.") or any(key in line for key in REMOVED_CONFIG):
            findings.append(f"{defaults.relative_to(root)}:{number}: removed driver/relay config")
    return sorted(set(findings))


def main() -> None:
    """Exit unsuccessfully while a removed owner or binding remains in production."""
    findings = violations()
    for finding in findings:
        print(finding)
    print(f"Task replacement removal guard: {len(findings)} violations")
    raise SystemExit(bool(findings))


if __name__ == "__main__":
    main()
