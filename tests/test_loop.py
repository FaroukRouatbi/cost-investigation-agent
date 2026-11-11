from collections.abc import Callable
from typing import Any

from cost_investigation_agent.agent.budget import Budget, BudgetLimits
from cost_investigation_agent.agent.loop import run_investigation
from cost_investigation_agent.agent.model import Message, ModelResponse, ToolCall, ToolSpec
from cost_investigation_agent.agent.registry import ToolRegistry
from cost_investigation_agent.tools.contracts import ToolError


class FakeModel:
    """Returns scripted responses in order and records what it was shown."""

    def __init__(self, *responses: ModelResponse) -> None:
        self._responses = list(responses)
        self.calls: list[list[Message]] = []

    def converse(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        self.calls.append(list(messages))
        return self._responses.pop(0)


class SlowModel(FakeModel):
    """Advances a fake clock by 30 seconds on every call."""

    def __init__(self, now: list[float], *responses: ModelResponse) -> None:
        super().__init__(*responses)
        self._now = now

    def converse(self, messages: list[Message], tools: list[ToolSpec]) -> ModelResponse:
        self._now[0] += 30.0
        return super().converse(messages, tools)


def answer(text: str) -> ModelResponse:
    return ModelResponse(text=text, tool_calls=(), input_tokens=10, output_tokens=5)


def call_tool(name: str, arguments: dict[str, Any], call_id: str = "c1") -> ModelResponse:
    return ModelResponse(
        text=None,
        tool_calls=(ToolCall(id=call_id, name=name, arguments=arguments),),
        input_tokens=10,
        output_tokens=5,
    )


def _boom() -> None:
    raise RuntimeError("internal detail that must not leak")


def make_registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        ToolSpec(name="echo", description="Echo a value", input_schema={}),
        lambda value: {"echo": value},
    )
    registry.register(
        ToolSpec(name="boom", description="Always crashes", input_schema={}),
        _boom,
    )
    registry.register(
        ToolSpec(name="fail", description="Returns a ToolError", input_schema={}),
        lambda: ToolError(code="nope", message="Nope."),
    )
    return registry


def budget(
    max_steps: int = 10,
    max_tokens: int = 100_000,
    timeout: float = 60.0,
    clock: Callable[[], float] | None = None,
) -> Budget:
    limits = BudgetLimits(max_steps=max_steps, max_tokens=max_tokens, timeout_seconds=timeout)
    if clock is None:
        return Budget(limits=limits)
    return Budget(limits=limits, clock=clock)


def test_answers_immediately_when_no_tools_needed() -> None:
    model = FakeModel(answer("Costs are flat."))
    report = run_investigation("Why did cost change?", model, make_registry(), budget())

    assert report.status == "complete"
    assert report.text == "Costs are flat."
    assert report.steps == 1
    assert report.stop_reason is None


def test_tool_result_is_fed_back_to_the_model() -> None:
    model = FakeModel(call_tool("echo", {"value": "hi"}), answer("Done."))
    report = run_investigation("q", model, make_registry(), budget())

    assert report.status == "complete"
    assert report.steps == 2
    tool_message = model.calls[1][-1]
    assert tool_message.role == "tool"
    assert tool_message.tool_results[0].content == {"echo": "hi"}
    assert tool_message.tool_results[0].is_error is False


def test_unknown_tool_becomes_error_result_not_a_crash() -> None:
    model = FakeModel(call_tool("delete_everything", {}), answer("Could not use that tool."))
    report = run_investigation("q", model, make_registry(), budget())

    assert report.status == "complete"
    result = model.calls[1][-1].tool_results[0]
    assert result.is_error is True
    assert result.content["code"] == "unknown_tool"


def test_wrong_arguments_become_error_result() -> None:
    model = FakeModel(call_tool("echo", {"wrong": "x"}), answer("Retrying."))
    report = run_investigation("q", model, make_registry(), budget())

    assert report.status == "complete"
    result = model.calls[1][-1].tool_results[0]
    assert result.is_error is True
    assert result.content["code"] == "bad_arguments"


def test_crashing_tool_hides_internal_detail() -> None:
    model = FakeModel(call_tool("boom", {}), answer("Tool failed."))
    report = run_investigation("q", model, make_registry(), budget())

    assert report.status == "complete"
    result = model.calls[1][-1].tool_results[0]
    assert result.is_error is True
    assert result.content["code"] == "tool_failed"
    assert "internal detail" not in str(result.content)


def test_tool_error_return_is_flagged_and_serialized() -> None:
    model = FakeModel(call_tool("fail", {}), answer("It failed."))
    run_investigation("q", model, make_registry(), budget())

    result = model.calls[1][-1].tool_results[0]
    assert result.is_error is True
    assert result.content == {"code": "nope", "message": "Nope."}


def test_step_limit_stops_run_and_marks_incomplete() -> None:
    model = FakeModel(
        call_tool("echo", {"value": "1"}),
        call_tool("echo", {"value": "2"}),
    )
    report = run_investigation("q", model, make_registry(), budget(max_steps=2))

    assert report.status == "incomplete"
    assert report.stop_reason == "max_steps"
    assert report.steps == 2
    assert len(model.calls) == 2


def test_token_limit_stops_run() -> None:
    model = FakeModel(call_tool("echo", {"value": "1"}), answer("never reached"))
    report = run_investigation("q", model, make_registry(), budget(max_tokens=10))

    assert report.status == "incomplete"
    assert report.stop_reason == "max_tokens"
    assert len(model.calls) == 1


def test_timeout_stops_run_using_injected_clock() -> None:
    now = [0.0]
    model = SlowModel(
        now,
        call_tool("echo", {"value": "1"}),
        call_tool("echo", {"value": "2"}),
        answer("never reached"),
    )
    report = run_investigation(
        "q",
        model,
        make_registry(),
        budget(timeout=60.0, clock=lambda: now[0]),
    )

    assert report.status == "incomplete"
    assert report.stop_reason == "timeout"
    assert len(model.calls) == 2


def test_zero_step_budget_makes_no_model_call() -> None:
    model = FakeModel()
    report = run_investigation("q", model, make_registry(), budget(max_steps=0))

    assert report.status == "incomplete"
    assert report.stop_reason == "max_steps"
    assert model.calls == []
