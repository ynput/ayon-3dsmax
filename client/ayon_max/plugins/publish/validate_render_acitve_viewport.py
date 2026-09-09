"""Validates whether the active viewport is set in render settings."""
import pyblish.api
from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin)
from ayon_core.pipeline.publish import RepairAction

try:
    from pymxs import runtime as rt
except ImportError:
    rt = None


class ValidateNoActiveViewport(pyblish.api.ContextPlugin,
                               OptionalPyblishPluginMixin):
    """Validates No Active Viewport

    Check if there is no active viewport set in the render settings.
    """

    order = pyblish.api.ValidatorOrder
    families = ["maxrender"]
    hosts = ["max"]
    label = "No Active Viewport"
    optional = False
    actions = [RepairAction]

    def process(self, context):
        if not self.is_active(context.data):
            return
        if not rt.rendUseActiveView:
            raise PublishValidationError(
                "No active viewport is set in the render settings."
            )

    @classmethod
    def repair(cls, context):
        rt.rendUseActiveView = True
        rt.renderSceneDialog.update()
