import re
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any, Protocol

from cost_investigation_agent.tools.contracts import MetricSummary, ToolError

ALLOWED_METRICS = frozenset({"CPUUtilization", "NetworkIn"})
MAX_RANGE_DAYS = 14
PERIOD_SECONDS = 3600

_INSTANCE_ID = re.compile(r"i-[0-9a-f]{8,17}")


class CloudWatchClient(Protocol):
    def get_metric_statistics(self, **kwargs: Any) -> dict[str, Any]: ...


def get_usage_metrics(
    client: CloudWatchClient,
    instance_id: str,
    metric: str,
    start: str,
    end: str,
) -> MetricSummary | ToolError:
    if not _INSTANCE_ID.fullmatch(instance_id):
        return ToolError(
            code="invalid_instance_id", message="Expected an EC2 instance ID like i-0abc123."
        )

    if metric not in ALLOWED_METRICS:
        return ToolError(
            code="invalid_metric",
            message=f"Metric must be one of: {', '.join(sorted(ALLOWED_METRICS))}.",
        )

    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return ToolError(code="invalid_date", message="Dates must be YYYY-MM-DD.")

    if start_date >= end_date:
        return ToolError(code="invalid_range", message="start must be before end.")

    if (end_date - start_date).days > MAX_RANGE_DAYS:
        return ToolError(
            code="range_too_long",
            message=f"Ranges are limited to {MAX_RANGE_DAYS} days.",
        )

    response = client.get_metric_statistics(
        Namespace="AWS/EC2",
        MetricName=metric,
        Dimensions=[{"Name": "InstanceId", "Value": instance_id}],
        StartTime=datetime.combine(start_date, time.min, tzinfo=UTC),
        EndTime=datetime.combine(end_date, time.min, tzinfo=UTC),
        Period=PERIOD_SECONDS,
        Statistics=["Average", "Maximum"],
    )

    points = response["Datapoints"]
    if not points:
        return MetricSummary(
            instance_id=instance_id,
            metric=metric,
            start=start,
            end=end,
            status="no_data",
            datapoint_count=0,
            average=None,
            maximum=None,
        )

    averages = [Decimal(str(p["Average"])) for p in points]
    maxima = [Decimal(str(p["Maximum"])) for p in points]

    return MetricSummary(
        instance_id=instance_id,
        metric=metric,
        start=start,
        end=end,
        status="ok",
        datapoint_count=len(points),
        average=(sum(averages, Decimal("0")) / len(averages)).quantize(Decimal("0.01")),
        maximum=max(maxima),
    )
