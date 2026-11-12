from dataclasses import dataclass
from typing import Literal

ActionType = Literal["stop_instance", "set_log_retention", "apply_tags"]
ProposalStatus = Literal["pending_approval", "approved", "rejected", "stale", "executed"]


@dataclass(frozen=True)
class Evidence:
    tool_name: str
    summary: str


@dataclass(frozen=True)
class Proposal:
    id: str
    action: ActionType
    target: str
    reason: str
    evidence: tuple[Evidence, ...]
    status: ProposalStatus = "pending_approval"
