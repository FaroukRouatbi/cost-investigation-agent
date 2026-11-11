from datetime import date
from decimal import Decimal
from typing import Any, Protocol

from cost_investigation_agent.tools.contracts import (
    CostBreakdown,
    CostRow,
    GroupBy,
    ToolError,
)

_DIMENSION_KEYS: dict[GroupBy, str] = {
    "SERVICE": "SERVICE",
    "REGION": "REGION",
}


class CostExplorerClient(Protocol):
    def get_cost_and_usage(self, **kwargs: Any) -> dict[str, Any]: ...


def get_cost_breakdown(
    client: CostExplorerClient,
    start: str,
    end: str,
    group_by: GroupBy,
) -> CostBreakdown | ToolError:
    try:
        start_date = date.fromisoformat(start)
        end_date = date.fromisoformat(end)
    except ValueError:
        return ToolError(code="invalid_date", message="Dates must be YYYY-MM-DD.")

    if start_date >= end_date:
        return ToolError(code="invalid_range", message="start must be before end.")

    response = client.get_cost_and_usage(
        TimePeriod={"Start": start, "End": end},
        Granularity="MONTHLY",
        Metrics=["UnblendedCost"],
        GroupBy=[{"Type": "DIMENSION", "Key": _DIMENSION_KEYS[group_by]}],
    )

    rows: list[CostRow] = []
    total = Decimal("0")
    for period in response["ResultsByTime"]:
        for group in period["Groups"]:
            amount = Decimal(group["Metrics"]["UnblendedCost"]["Amount"])
            rows.append(CostRow(group=group["Keys"][0], cost_usd=amount))
            total += amount

    rows.sort(key=lambda row: row.cost_usd, reverse=True)
    return CostBreakdown(
        start=start,
        end=end,
        group_by=group_by,
        total_usd=total,
        rows=tuple(rows),
    )
