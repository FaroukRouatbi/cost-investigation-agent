import re
from typing import Any, cast, get_args

from cost_investigation_agent.approval.proposal import ActionType, Evidence, Proposal
from cost_investigation_agent.tools.contracts import ToolError

ALLOWED_ACTIONS: frozenset[str] = frozenset(get_args(ActionType))
MAX_REASON_CHARS = 1000
MAX_EVIDENCE_ITEMS = 10

_INSTANCE_ID = re.compile(r"i-[0-9a-f]{8,17}")
_LOG_GROUP = re.compile(r"/[A-Za-z0-9._/#-]{1,511}")

_TARGET_RULES: dict[str, re.Pattern[str]] = {
    "stop_instance": _INSTANCE_ID,
    "apply_tags": _INSTANCE_ID,
    "set_log_retention": _LOG_GROUP,
}


def validate_proposal(raw: Any, proposal_id: str) -> Proposal | ToolError:
    if not isinstance(raw, dict):
        return ToolError(code="not_an_object", message="A proposal must be a JSON object.")

    action = raw.get("action")
    if not isinstance(action, str) or action not in ALLOWED_ACTIONS:
        allowed = ", ".join(sorted(ALLOWED_ACTIONS))
        return ToolError(code="action_not_allowed", message=f"Action must be one of: {allowed}.")

    target = raw.get("target")
    if not isinstance(target, str) or not _TARGET_RULES[action].fullmatch(target):
        return ToolError(code="bad_target", message="Target has the wrong format for this action.")

    reason = raw.get("reason")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > MAX_REASON_CHARS:
        return ToolError(
            code="bad_reason",
            message=f"Reason must be 1 to {MAX_REASON_CHARS} characters.",
        )

    bad_evidence = ToolError(
        code="bad_evidence",
        message=f"Evidence must be 1 to {MAX_EVIDENCE_ITEMS} items, "
        "each with a tool_name and summary.",
    )
    evidence = raw.get("evidence")
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_EVIDENCE_ITEMS:
        return bad_evidence

    items: list[Evidence] = []
    for item in evidence:
        if not isinstance(item, dict):
            return bad_evidence
        tool_name = item.get("tool_name")
        summary = item.get("summary")
        if not isinstance(tool_name, str) or not isinstance(summary, str) or not summary.strip():
            return bad_evidence
        items.append(Evidence(tool_name=tool_name, summary=summary))

    return Proposal(
        id=proposal_id,
        action=cast(ActionType, action),
        target=target,
        reason=reason,
        evidence=tuple(items),
    )
