from __future__ import annotations

from typing import Any

from pymxs import runtime as rt

from ayon_core.pipeline import InventoryAction


class LockVersions(InventoryAction):
    """Lock container versions using persistent 3ds Max user properties."""

    label = "Lock versions"
    icon = "lock"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container: dict[str, Any]) -> bool:
        return container.get("version_locked") is not True

    def process(self, containers: list[dict[str, Any]]) -> bool:
        for container in containers:
            if container.get("version_locked") is True:
                continue
            node_name = container["objectName"]
            node = rt.GetNodeByName(node_name)
            if node is None:
                raise RuntimeError(
                    f"Cannot lock version: container '{node_name}' not found."
                )
            rt.SetUserProp(node, "version_locked", True)
        return True


class UnlockVersions(InventoryAction):
    """Remove the version lock from a container's user properties."""

    label = "Unlock versions"
    icon = "lock-open"
    color = "#ffffff"
    order = -1

    @staticmethod
    def is_compatible(container: dict[str, Any]) -> bool:
        return container.get("version_locked") is True

    def process(self, containers: list[dict[str, Any]]) -> bool:
        for container in containers:
            if container.get("version_locked") is not True:
                continue
            node_name = container["objectName"]
            node = rt.GetNodeByName(node_name)
            if node is None:
                raise RuntimeError(
                    f"Cannot unlock version: container '{node_name}' not found."
                )
            if rt.getUserProp(node, "version_locked") is not None:
                rt.deleteUserProp(node, "version_locked")
        return True
