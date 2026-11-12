from cost_investigation_agent.approval.proposal import Proposal
from cost_investigation_agent.approval.validator import validate_proposal
from cost_investigation_agent.tools.contracts import ToolError

EVIDENCE = [{"tool_name": "get_usage_metrics", "summary": "CPU averaged 1.1% over 24h"}]


def proposal_dict(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "action": "stop_instance",
        "target": "i-0aaa1111bbb222333",
        "reason": "Idle for 24 hours.",
        "evidence": EVIDENCE,
    }
    base.update(overrides)
    return base


def test_valid_stop_instance_passes_as_pending() -> None:
    result = validate_proposal(proposal_dict(), proposal_id="p-1")

    assert isinstance(result, Proposal)
    assert result.status == "pending_approval"
    assert result.id == "p-1"


def test_valid_log_retention_passes() -> None:
    raw = proposal_dict(
        action="set_log_retention",
        target="/aws/lambda/search-api",
    )
    result = validate_proposal(raw, proposal_id="p-2")

    assert isinstance(result, Proposal)
    assert result.action == "set_log_retention"


def test_action_outside_allowlist_rejected() -> None:
    result = validate_proposal(proposal_dict(action="terminate_instance"), proposal_id="p-3")

    assert isinstance(result, ToolError)
    assert result.code == "action_not_allowed"


def test_instance_action_requires_instance_id() -> None:
    result = validate_proposal(proposal_dict(target="/aws/lambda/search-api"), proposal_id="p-4")

    assert isinstance(result, ToolError)
    assert result.code == "bad_target"


def test_log_retention_requires_log_group_path() -> None:
    raw = proposal_dict(action="set_log_retention", target="i-0aaa1111bbb222333")
    result = validate_proposal(raw, proposal_id="p-5")

    assert isinstance(result, ToolError)
    assert result.code == "bad_target"


def test_empty_reason_rejected() -> None:
    result = validate_proposal(proposal_dict(reason="   "), proposal_id="p-6")

    assert isinstance(result, ToolError)
    assert result.code == "bad_reason"


def test_missing_evidence_rejected() -> None:
    result = validate_proposal(proposal_dict(evidence=[]), proposal_id="p-7")

    assert isinstance(result, ToolError)
    assert result.code == "bad_evidence"


def test_non_object_rejected() -> None:
    result = validate_proposal("stop everything", proposal_id="p-8")

    assert isinstance(result, ToolError)
    assert result.code == "not_an_object"
