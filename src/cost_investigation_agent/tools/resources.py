import re
from typing import Any, Protocol

from cost_investigation_agent.tools.contracts import (
    InstanceInfo,
    ResourceInventory,
    ToolError,
)

MAX_INSTANCES = 50

_TAG_KEY = re.compile(r"[A-Za-z0-9 _.:/=+@-]{1,128}")
_TAG_VALUE = re.compile(r"[A-Za-z0-9 _.:/=+@-]{0,256}")


class EC2Client(Protocol):
    def describe_instances(self, **kwargs: Any) -> dict[str, Any]: ...


def _name_from_tags(tags: list[dict[str, str]]) -> str | None:
    for tag in tags:
        if tag["Key"] == "Name":
            return tag["Value"]
    return None


def describe_resources(
    client: EC2Client,
    tag_key: str,
    tag_value: str,
) -> ResourceInventory | ToolError:
    if not _TAG_KEY.fullmatch(tag_key):
        return ToolError(
            code="invalid_tag_key", message="Tag key has invalid characters or length."
        )

    if not _TAG_VALUE.fullmatch(tag_value):
        return ToolError(
            code="invalid_tag_value", message="Tag value has invalid characters or length."
        )

    response = client.describe_instances(
        Filters=[{"Name": f"tag:{tag_key}", "Values": [tag_value]}],
        MaxResults=MAX_INSTANCES + 1,
    )

    found: list[InstanceInfo] = []
    for reservation in response["Reservations"]:
        for inst in reservation["Instances"]:
            tags: list[dict[str, str]] = inst.get("Tags", [])
            found.append(
                InstanceInfo(
                    instance_id=inst["InstanceId"],
                    instance_type=inst["InstanceType"],
                    state=inst["State"]["Name"],
                    name=_name_from_tags(tags),
                    tags=tuple((t["Key"], t["Value"]) for t in tags),
                )
            )

    truncated = len(found) > MAX_INSTANCES
    return ResourceInventory(
        tag_key=tag_key,
        tag_value=tag_value,
        instances=tuple(found[:MAX_INSTANCES]),
        truncated=truncated,
    )
