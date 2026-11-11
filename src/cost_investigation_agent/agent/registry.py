from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from cost_investigation_agent.agent.model import ToolSpec


@dataclass(frozen=True)
class RegisteredTool:
    spec: ToolSpec
    run: Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, spec: ToolSpec, run: Callable[..., Any]) -> None:
        if spec.name in self._tools:
            raise ValueError(f"Tool already registered: {spec.name}")
        self._tools[spec.name] = RegisteredTool(spec=spec, run=run)

    def get(self, name: str) -> RegisteredTool | None:
        return self._tools.get(name)

    def specs(self) -> list[ToolSpec]:
        return [tool.spec for tool in self._tools.values()]
