from dataclasses import dataclass
from typing import Any, Literal, Protocol

Role = Literal["user", "assistant", "tool"]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    call_id: str
    content: dict[str, Any]
    is_error: bool = False


@dataclass(frozen=True)
class Message:
    role: Role
    text: str | None = None
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()


@dataclass(frozen=True)
class ModelResponse:
    text: str | None
    tool_calls: tuple[ToolCall, ...]
    input_tokens: int
    output_tokens: int


class ModelClient(Protocol):
    def converse(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse: ...
