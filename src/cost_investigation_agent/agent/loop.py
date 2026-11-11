import inspect
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
from typing import Any, Literal

import structlog

from cost_investigation_agent.agent.budget import Budget, StopReason
from cost_investigation_agent.agent.model import Message, ModelClient, ToolCall, ToolResult
from cost_investigation_agent.agent.registry import ToolRegistry
from cost_investigation_agent.tools.contracts import ToolError

log = structlog.get_logger()

RunStatus = Literal["complete", "incomplete"]


@dataclass(frozen=True)
class Report:
    status: RunStatus
    text: str | None
    stop_reason: StopReason | None
    steps: int
    tokens: int


def to_jsonable(value: object) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, tuple | list):
        return [to_jsonable(item) for item in value]
    return value


def run_tool(call: ToolCall, registry: ToolRegistry) -> ToolResult:
    tool = registry.get(call.name)
    if tool is None:
        return ToolResult(
            call_id=call.id,
            content={"code": "unknown_tool", "message": f"No tool named {call.name}."},
            is_error=True,
        )

    try:
        inspect.signature(tool.run).bind(**call.arguments)
    except TypeError as exc:
        return ToolResult(
            call_id=call.id,
            content={"code": "bad_arguments", "message": str(exc)},
            is_error=True,
        )

    try:
        result = tool.run(**call.arguments)
    except Exception:
        log.exception("tool_crashed", tool=call.name)
        return ToolResult(
            call_id=call.id,
            content={"code": "tool_failed", "message": "The tool failed unexpectedly."},
            is_error=True,
        )

    return ToolResult(
        call_id=call.id,
        content=to_jsonable(result),
        is_error=isinstance(result, ToolError),
    )


def run_investigation(
    question: str,
    model: ModelClient,
    registry: ToolRegistry,
    budget: Budget,
) -> Report:
    messages: list[Message] = [Message(role="user", text=question)]
    last_text: str | None = None

    while True:
        stop = budget.exhausted()
        if stop is not None:
            log.warning("run_stopped", reason=stop, steps=budget.steps)
            return Report(
                status="incomplete",
                text=last_text,
                stop_reason=stop,
                steps=budget.steps,
                tokens=budget.tokens,
            )

        response = model.converse(messages, registry.specs())
        budget.record_step(response.input_tokens, response.output_tokens)
        if response.text is not None:
            last_text = response.text

        if not response.tool_calls:
            return Report(
                status="complete",
                text=response.text,
                stop_reason=None,
                steps=budget.steps,
                tokens=budget.tokens,
            )

        messages.append(
            Message(role="assistant", text=response.text, tool_calls=response.tool_calls)
        )
        results = tuple(run_tool(call, registry) for call in response.tool_calls)
        messages.append(Message(role="tool", tool_results=results))
