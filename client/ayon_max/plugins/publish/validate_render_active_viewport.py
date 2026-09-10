"""Validates whether the render active viewport is set in render settings."""
import pyblish.api
from ayon_core.pipeline import (
    PublishValidationError,
    OptionalPyblishPluginMixin)
from ayon_core.pipeline.publish import RepairAction
from pymxs import runtime as rt


class ValidateNoActiveViewport(pyblish.api.ContextPlugin,
                               OptionalPyblishPluginMixin):
    """Validates No Active Viewport

    Check if there is no active viewport set in the render settings.
    """

    order = pyblish.api.ValidatorOrder
    families = ["maxrender"]
    hosts = ["max"]
    label = "No Render Active Viewport"
    optional = False
    actions = [RepairAction]

    def process(self, context):
        if not self.is_active(context.data):
            return
        if not rt.rendUseActiveView:
            raise PublishValidationError(
                title="Render active viewport disabled in the render settings",
                message=(
                    "We need to enable 'render active viewport' in the render settings"
                    " to make sure the correct render viewport is used. Please use repair"
                    " action to activate it."
                )
            )

    @classmethod
    def repair(cls, context):
        rt.rendUseActiveView = True
        rt.renderSceneDialog.update()
