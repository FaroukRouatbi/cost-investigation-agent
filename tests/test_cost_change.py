import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from cost_investigation_agent.tools.contracts import CostChange, ToolError
from cost_investigation_agent.tools.cost_change import get_cost_change

FIXTURES = Path(__file__).parent / "fixtures"


class SequenceCostExplorer:
    """Returns one fixture per call, in call order: previous period, then current."""

    def __init__(self, *fixtures: str) -> None:
        self._responses: list[dict[str, Any]] = [
            json.loads((FIXTURES / f).read_text()) for f in fixtures
        ]
        self.calls: list[dict[str, Any]] = []

    def get_cost_and_usage(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        response: dict[str, Any] = self._responses[len(self.calls) - 1]
        return response


def test_new_service_appears_as_change_from_zero() -> None:
    client = SequenceCostExplorer("baseline.json", "nat_gateway_spike.json")
    result = get_cost_change(
        client,
        "2026-09-01",
        "2026-10-01",
        "2026-10-01",
        "2026-11-01",
        "SERVICE",
    )

    assert isinstance(result, CostChange)
    assert result.previous_total_usd == Decimal("207.85")
    assert result.current_total_usd == Decimal("517.85")

    nat = next(r for r in result.rows if r.group == "EC2 - Other")
    assert nat.previous_usd == Decimal("0")
    assert nat.current_usd == Decimal("310.00")
    assert nat.change_usd == Decimal("310.00")
    assert nat.change_pct is None


def test_largest_change_is_ranked_first() -> None:
    client = SequenceCostExplorer("baseline.json", "nat_gateway_spike.json")
    result = get_cost_change(
        client,
        "2026-09-01",
        "2026-10-01",
        "2026-10-01",
        "2026-11-01",
        "SERVICE",
    )

    assert isinstance(result, CostChange)
    assert result.rows[0].group == "EC2 - Other"
    assert result.rows[0].change_usd == Decimal("310.00")


def test_percentage_change_for_existing_service() -> None:
    client = SequenceCostExplorer("baseline.json", "runaway_lambda.json")
    result = get_cost_change(
        client,
        "2026-09-01",
        "2026-10-01",
        "2026-10-01",
        "2026-11-01",
        "SERVICE",
    )

    assert isinstance(result, CostChange)
    lam = next(r for r in result.rows if r.group == "AWS Lambda")
    assert lam.previous_usd == Decimal("5.25")
    assert lam.current_usd == Decimal("240.00")
    assert lam.change_usd == Decimal("234.75")
    assert lam.change_pct == Decimal("4471.43")


def test_overlapping_periods_rejected_without_calling_aws() -> None:
    client = SequenceCostExplorer()
    result = get_cost_change(
        client,
        "2026-10-01",
        "2026-11-01",
        "2026-10-15",
        "2026-11-15",
        "SERVICE",
    )

    assert isinstance(result, ToolError)
    assert result.code == "overlapping_periods"
    assert client.calls == []
