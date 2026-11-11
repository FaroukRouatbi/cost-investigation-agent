from datetime import date
from decimal import Decimal

from cost_investigation_agent.tools.contracts import (
    CostChange,
    CostChangeRow,
    GroupBy,
    ToolError,
)
from cost_investigation_agent.tools.cost_breakdown import (
    CostExplorerClient,
    get_cost_breakdown,
)


def _overlaps(a_start: date, a_end: date, b_start: date, b_end: date) -> bool:
    return a_start < b_end and b_start < a_end


def get_cost_change(
    client: CostExplorerClient,
    previous_start: str,
    previous_end: str,
    current_start: str,
    current_end: str,
    group_by: GroupBy,
) -> CostChange | ToolError:
    try:
        prev_s = date.fromisoformat(previous_start)
        prev_e = date.fromisoformat(previous_end)
        curr_s = date.fromisoformat(current_start)
        curr_e = date.fromisoformat(current_end)
    except ValueError:
        return ToolError(code="invalid_date", message="Dates must be YYYY-MM-DD.")

    if _overlaps(prev_s, prev_e, curr_s, curr_e):
        return ToolError(
            code="overlapping_periods",
            message="The two periods must not overlap.",
        )

    # Previous period is queried first. The test stub relies on this order.
    previous = get_cost_breakdown(client, previous_start, previous_end, group_by)
    if isinstance(previous, ToolError):
        return previous

    current = get_cost_breakdown(client, current_start, current_end, group_by)
    if isinstance(current, ToolError):
        return current

    previous_by_group = {row.group: row.cost_usd for row in previous.rows}
    current_by_group = {row.group: row.cost_usd for row in current.rows}

    rows: list[CostChangeRow] = []
    for group in sorted(previous_by_group.keys() | current_by_group.keys()):
        before = previous_by_group.get(group, Decimal("0"))
        after = current_by_group.get(group, Decimal("0"))
        change = after - before
        pct: Decimal | None = None
        if before != 0:
            pct = (change / before * 100).quantize(Decimal("0.01"))
        rows.append(
            CostChangeRow(
                group=group,
                previous_usd=before,
                current_usd=after,
                change_usd=change,
                change_pct=pct,
            )
        )

    rows.sort(key=lambda r: (-abs(r.change_usd), r.group))

    return CostChange(
        previous_start=previous_start,
        previous_end=previous_end,
        current_start=current_start,
        current_end=current_end,
        group_by=group_by,
        previous_total_usd=previous.total_usd,
        current_total_usd=current.total_usd,
        rows=tuple(rows),
    )
