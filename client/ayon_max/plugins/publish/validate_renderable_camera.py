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
        if self.get_invalid_cmaera_nodes(instance):
            raise PublishValidationError(
                "No renderable Camera found in scene."
            )
        if self.get_mismatch_camera(instance):
            raise PublishValidationError(
                "The current viewport camera does not match "
                "the target renderable camera."
            )

    @classmethod
    def get_invalid_cmaera_nodes(cls, instance):
        if not instance.data["cameras"]:
           return True
        return False

    @classmethod
    def get_mismatch_camera(cls, instance):
        if instance.data["multiCamera"]:
            cls.log.warning("Multiple cameras detected in the scene. Skipping validation.")
            return None
        camera_name = next(iter(instance.data["cameras"]))
        viewport_camera = rt.viewport.GetCamera()
        target_camera = rt.getNodeByName(camera_name)
        if viewport_camera != target_camera:
            return camera_name
        return None

    @classmethod
    def repair(cls, instance):
        invalid_camera_nodes = cls.get_invalid_cmaera_nodes(instance)
        if invalid_camera_nodes:
            rt.viewport.setType(rt.Name("view_camera"))
            camera = rt.viewport.GetCamera()
            cls.log.info(f"Camera {camera} set as renderable camera")
            cls._set_arnold_camera(camera)
            instance.data["cameras"] = [camera.name]
            return
        mismatch_camera = cls.get_mismatch_camera(instance)
        if mismatch_camera:
            rt.viewport.setCamera(rt.getNodeByName(mismatch_camera))
            cls.log.info(f"Camera {mismatch_camera} set as renderable camera")
            cls._set_arnold_camera(rt.getNodeByName(mismatch_camera))
            instance.data["cameras"] = [mismatch_camera]

    @classmethod
    def _set_arnold_camera(cls, camera):
        renderer_class = get_current_renderer()
        renderer = str(renderer_class).split(":")[0]
        if renderer == "Arnold":
            arv = rt.MAXToAOps.ArnoldRenderView()
            arv.setOption("Camera", str(camera))
            arv.close()
