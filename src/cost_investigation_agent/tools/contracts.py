from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

GroupBy = Literal["SERVICE", "REGION"]
MetricName = Literal["CPUUtilization", "NetworkIn"]
MetricStatus = Literal["ok", "no_data"]


@dataclass(frozen=True)
class CostRow:
    group: str
    cost_usd: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    start: str
    end: str
    group_by: GroupBy
    total_usd: Decimal
    rows: tuple[CostRow, ...]


@dataclass(frozen=True)
class ToolError:
    code: str
    message: str


@dataclass(frozen=True)
class CostChangeRow:
    group: str
    previous_usd: Decimal
    current_usd: Decimal
    change_usd: Decimal
    change_pct: Decimal | None


@dataclass(frozen=True)
class CostChange:
    previous_start: str
    previous_end: str
    current_start: str
    current_end: str
    group_by: GroupBy
    previous_total_usd: Decimal
    current_total_usd: Decimal
    rows: tuple[CostChangeRow, ...]


@dataclass(frozen=True)
class MetricSummary:
    instance_id: str
    metric: str
    start: str
    end: str
    status: MetricStatus
    datapoint_count: int
    average: Decimal | None
    maximum: Decimal | None


@dataclass(frozen=True)
class InstanceInfo:
    instance_id: str
    instance_type: str
    state: str
    name: str | None
    tags: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ResourceInventory:
    tag_key: str
    tag_value: str
    instances: tuple[InstanceInfo, ...]
    truncated: bool
