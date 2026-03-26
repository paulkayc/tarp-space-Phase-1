from __future__ import annotations


def append_action_log(context: dict) -> dict:
    logs = list(context.get("action_logs", []))
    logs.append(context.get("action_message", "action_executed"))
    context["action_logs"] = logs
    return context
