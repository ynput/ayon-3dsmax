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
                title="No Active Render Viewport",
                message=(
                    "The render active viewport is currently disabled "
                    "in the render settings. Please use the repair action "
                    "to activate it."
                ),
                description=(
                    "## Render Active Render Viewport\n"
                    "The render active viewport is currently "
                    "disabled in the render settings.\n\n"
                    "We need to enable the render active viewport "
                    "to ensure the correct render viewport is used.\n\n"
                    "You can use the repair action to activate it."
                )

            )

    @classmethod
    def repair(cls, context):
        rt.rendUseActiveView = True
