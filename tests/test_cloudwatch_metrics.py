import json
from decimal import Decimal
from pathlib import Path
from typing import Any

from cost_investigation_agent.tools.cloudwatch_metrics import get_usage_metrics
from cost_investigation_agent.tools.contracts import MetricSummary, ToolError

FIXTURES = Path(__file__).parent / "fixtures"
INSTANCE = "i-0abc1234def567890"


class StubCloudWatch:
    def __init__(self, fixture: str | None = None) -> None:
        self._response: dict[str, Any] = (
            json.loads((FIXTURES / fixture).read_text()) if fixture else {"Datapoints": []}
        )
        self.calls: list[dict[str, Any]] = []

    def get_metric_statistics(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self._response


def test_idle_instance_summary() -> None:
    client = StubCloudWatch("cloudwatch_idle.json")
    result = get_usage_metrics(client, INSTANCE, "CPUUtilization", "2026-10-01", "2026-10-02")

    assert isinstance(result, MetricSummary)
    assert result.status == "ok"
    assert result.datapoint_count == 2
    assert result.average == Decimal("1.10")
    assert result.maximum == Decimal("3.0")


def test_busy_instance_summary() -> None:
    client = StubCloudWatch("cloudwatch_busy.json")
    result = get_usage_metrics(client, INSTANCE, "CPUUtilization", "2026-10-01", "2026-10-02")

    assert isinstance(result, MetricSummary)
    assert result.average == Decimal("75.00")
    assert result.maximum == Decimal("95.0")


def test_no_datapoints_is_a_result_not_an_error() -> None:
    client = StubCloudWatch("cloudwatch_no_data.json")
    result = get_usage_metrics(client, INSTANCE, "CPUUtilization", "2026-10-01", "2026-10-02")

    assert isinstance(result, MetricSummary)
    assert result.status == "no_data"
    assert result.average is None
    assert result.maximum is None


def test_invalid_instance_id_rejected_without_calling_aws() -> None:
    client = StubCloudWatch()
    result = get_usage_metrics(client, "not-an-id", "CPUUtilization", "2026-10-01", "2026-10-02")

    assert isinstance(result, ToolError)
    assert result.code == "invalid_instance_id"
    assert client.calls == []


def test_unknown_metric_rejected_without_calling_aws() -> None:
    client = StubCloudWatch()
    result = get_usage_metrics(client, INSTANCE, "DiskWriteBytes", "2026-10-01", "2026-10-02")

    assert isinstance(result, ToolError)
    assert result.code == "invalid_metric"
    assert client.calls == []


def test_range_over_limit_rejected_without_calling_aws() -> None:
    client = StubCloudWatch()
    result = get_usage_metrics(client, INSTANCE, "CPUUtilization", "2026-10-01", "2026-11-01")

    assert isinstance(result, ToolError)
    assert result.code == "range_too_long"
    assert client.calls == []
