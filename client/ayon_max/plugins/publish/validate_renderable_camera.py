# -*- coding: utf-8 -*-
import pyblish.api
from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin)
from ayon_core.pipeline.publish import RepairAction
from ayon_max.api.lib import get_current_renderer

from pymxs import runtime as rt


class ValidateRenderableCamera(pyblish.api.InstancePlugin,
                               OptionalPyblishPluginMixin):
    """Validates Renderable Camera

    Check if the renderable camera used for rendering
    """

    order = pyblish.api.ValidatorOrder
    families = ["maxrender"]
    hosts = ["max"]
    label = "Renderable Camera"
    optional = True
    actions = [RepairAction]

    def process(self, instance):
        if not self.is_active(instance.data):
            return
        cameras = instance.data.get("cameras") or []
        if not cameras:
            raise PublishValidationError(
                title="No renderable camera",
                message=(
                    "No renderable camera found in the scene. A render "
                    "without a camera uses the active viewport (a perspective "
                    "view) instead, locally and on the farm."
                ),
                description=(
                    "## No renderable camera\n"
                    "The render instance has no camera assigned. Every render "
                    "has to be submitted with an explicit camera, otherwise "
                    "the render falls back to the perspective view of the "
                    "active viewport.\n\n"
                    "Assign a camera to the render instance, or use the "
                    "repair action to set the current viewport camera."
                ),
            )

        invalid_cameras = [
            camera_name for camera_name in cameras
            if not self._is_camera_node(camera_name)
        ]
        if invalid_cameras:
            raise PublishValidationError(
                title="Camera not found",
                message=(
                    "Camera(s) assigned to the render instance do not exist "
                    "in the scene: {}.".format(", ".join(invalid_cameras))
                ),
                description=(
                    "## Camera not found\n"
                    "The render instance refers to camera(s) which cannot be "
                    "found in the scene:\n\n"
                    + "\n".join(
                        f"- `{name}`" for name in invalid_cameras
                    )
                    + "\n\nReassign the cameras of the render instance."
                ),
            )

    @staticmethod
    def _is_camera_node(camera_name):
        """Check that a camera name refers to a camera node in the scene."""
        node = rt.getNodeByName(camera_name)
        return node is not None and rt.classOf(node) in rt.Camera.classes

    @classmethod
    def repair(cls, instance):
        rt.viewport.setType(rt.Name("view_camera"))
        camera = rt.viewport.GetCamera()
        cls.log.info(f"Camera {camera} set as renderable camera")
        renderer_class = get_current_renderer()
        renderer = str(renderer_class).split(":")[0]
        if renderer == "Arnold":
            arv = rt.MAXToAOps.ArnoldRenderView()
            arv.setOption("Camera", str(camera))
            arv.close()
        instance.data["cameras"] = [camera.name]
