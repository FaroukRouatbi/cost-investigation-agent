import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

StopReason = Literal["max_steps", "max_tokens", "timeout"]
Clock = Callable[[], float]


@dataclass(frozen=True)
class BudgetLimits:
    max_steps: int
    max_tokens: int
    timeout_seconds: float


@dataclass
class Budget:
    limits: BudgetLimits
    clock: Clock = field(default=time.monotonic)
    steps: int = 0
    tokens: int = 0
    _started_at: float = field(init=False)

    def __post_init__(self) -> None:
        self._started_at = self.clock()

    def record_step(self, input_tokens: int, output_tokens: int) -> None:
        self.steps += 1
        self.tokens += input_tokens + output_tokens

    def exhausted(self) -> StopReason | None:
        if self.steps >= self.limits.max_steps:
            return "max_steps"
        if self.tokens >= self.limits.max_tokens:
            return "max_tokens"
        if self.clock() - self._started_at >= self.limits.timeout_seconds:
            return "timeout"
        return None
