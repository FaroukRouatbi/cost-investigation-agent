import json
from pathlib import Path
from typing import Any

from cost_investigation_agent.tools.contracts import ResourceInventory, ToolError
from cost_investigation_agent.tools.resources import MAX_INSTANCES, describe_resources

FIXTURES = Path(__file__).parent / "fixtures"


class StubEC2:
    def __init__(self, fixture: str | None = None) -> None:
        self._response: dict[str, Any] = (
            json.loads((FIXTURES / fixture).read_text()) if fixture else {"Reservations": []}
        )
        self.calls: list[dict[str, Any]] = []

    def describe_instances(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return self._response


def test_lists_instances_with_names_and_states() -> None:
    client = StubEC2("ec2_describe.json")
    result = describe_resources(client, "team", "search")

    assert isinstance(result, ResourceInventory)
    assert len(result.instances) == 2
    assert result.instances[0].name == "search-api-1"
    assert result.instances[0].state == "running"
    assert result.instances[1].name is None
    assert result.instances[1].state == "stopped"
    assert result.truncated is False


def test_filter_uses_tag_syntax() -> None:
    client = StubEC2("ec2_describe.json")
    describe_resources(client, "team", "search")

    assert client.calls[0]["Filters"] == [{"Name": "tag:team", "Values": ["search"]}]


def test_truncation_flag_set_when_over_limit() -> None:
    client = StubEC2()
    instances = [
        {
            "InstanceId": f"i-{n:017x}",
            "InstanceType": "t3.micro",
            "State": {"Name": "running"},
            "Tags": [],
        }
        for n in range(MAX_INSTANCES + 1)
    ]
    client._response = {"Reservations": [{"Instances": instances}]}

    result = describe_resources(client, "team", "search")

    assert isinstance(result, ResourceInventory)
    assert len(result.instances) == MAX_INSTANCES
    assert result.truncated is True


def test_invalid_tag_key_rejected_without_calling_aws() -> None:
    client = StubEC2()
    result = describe_resources(client, "team;rm -rf", "search")

    assert isinstance(result, ToolError)
    assert result.code == "invalid_tag_key"
    assert client.calls == []


def test_empty_result_is_not_an_error() -> None:
    client = StubEC2()
    result = describe_resources(client, "team", "nobody")

    assert isinstance(result, ResourceInventory)
    assert result.instances == ()
    assert result.truncated is False
