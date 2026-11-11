import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from cost_investigation_agent.tools.contracts import CostBreakdown, ToolError
from cost_investigation_agent.tools.cost_breakdown import get_cost_breakdown

FIXTURES = Path(__file__).parent / "fixtures"


class StubCostExplorer:
    def __init__(self, fixture: str) -> None:
        self._response: dict[str, Any] = json.loads((FIXTURES / fixture).read_text())
        self.calls: list[dict[str, Any]] = []

    def get_cost_and_usage(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self._response


def test_baseline_total_and_top_row() -> None:
    client = StubCostExplorer("baseline.json")
    result = get_cost_breakdown(client, "2026-10-01", "2026-11-01", "SERVICE")

    assert isinstance(result, CostBreakdown)
    assert result.total_usd == Decimal("207.85")
    assert result.rows[0].group == "Amazon EC2"


def test_nat_spike_is_visible_as_top_row() -> None:
    client = StubCostExplorer("nat_gateway_spike.json")
    result = get_cost_breakdown(client, "2026-10-01", "2026-11-01", "SERVICE")

    assert isinstance(result, CostBreakdown)
    assert result.total_usd == Decimal("517.85")
    assert result.rows[0].group == "EC2 - Other"


def test_runaway_lambda_total() -> None:
    client = StubCostExplorer("runaway_lambda.json")
    result = get_cost_breakdown(client, "2026-10-01", "2026-11-01", "SERVICE")

    assert isinstance(result, CostBreakdown)
    assert result.total_usd == Decimal("442.60")


def test_invalid_date_returns_error_without_calling_aws() -> None:
    client = StubCostExplorer("baseline.json")
    result = get_cost_breakdown(client, "10/01/2026", "2026-11-01", "SERVICE")

    assert isinstance(result, ToolError)
    assert result.code == "invalid_date"
    assert client.calls == []


def test_reversed_range_returns_error() -> None:
    client = StubCostExplorer("baseline.json")
    result = get_cost_breakdown(client, "2026-11-01", "2026-10-01", "SERVICE")

    assert isinstance(result, ToolError)
    assert result.code == "invalid_range"
