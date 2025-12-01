# -*- coding: utf-8 -*-
import pyblish.api

from ayon_core.pipeline import PublishValidationError


class ValidateCameraContent(pyblish.api.InstancePlugin):
    """Validates Camera instance contents.

    A Camera instance may only hold a SINGLE camera's transform
    """

    order = pyblish.api.ValidatorOrder
    families = ["camera", "review"]
    hosts = ["max"]
    label = "Camera Contents"

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(("Camera instance must only include"
                                          "camera (and camera target). "
                                          f"Invalid content {invalid}"))

    def get_invalid(self, instance):
        """Get invalid nodes that are not cameras or valid containers."""
        from pymxs import runtime as rt

        container = instance.data["instance_node"]
        self.log.info(f"Validating camera content for {container}")

        invalid = []
        members = instance.data["members"]

        for member in members:
            if self._is_valid_member(member, rt):
                continue
            invalid.append(member)

        return invalid

    @staticmethod
    def _is_valid_member(node, rt):
        """Check if a node is a valid camera or alembic container with cameras."""
        # Direct camera check
        if rt.classof(node) in rt.Camera.classes:
            return True

        # Alembic container check
        if rt.classOf(node) == rt.AlembicContainer:
            return any(
                rt.classof(child) in rt.Camera.classes
                for child in node.children
            )

        return False
