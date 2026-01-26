"""Plugin to set context variables for workfile build in 3ds Max."""
from ayon_max.api.workfile_template_builder import (
    MaxPlaceholderPlugin
)
from ayon_max.api.lib import set_context_settings
from ayon_core.lib import BoolDef


class SetContextMaxPlaceholderPlugin(MaxPlaceholderPlugin):
    """Set context variables for the workfile build.
    This placeholder allows the workfile build process to
    set context variables dynamically.

    """

    identifier = "max.set_context"
    label = "Set Context Settings"

    use_selection_as_parent = False

    def get_placeholder_options(self, options=None):
        options = options or {}
        return [
            BoolDef(
                "resolution",
                label="Set Resolution",
                tooltip="Set Resolution context variable "
                        "based on the scene settings",
                default=options.get("resolution", True),
            ),
            BoolDef(
                "frame_range",
                label="Set Frame Range",
                tooltip="Set Frame Range context variable "
                        "based on the scene settings",
                default=options.get("frame_range", True),
            ),
            BoolDef(
                "colorspace",
                label="Set Colorspace",
                tooltip="Set Colorspace context variable "
                        "based on the scene settings",
                default=options.get("colorspace", True),
            ),
            BoolDef(
                "scene_units",
                label="Set Scene Units",
                tooltip="Set Scene Units context variable "
                        "based on the scene settings",
                default=options.get("scene_units", False),
            )
        ]

    def populate_placeholder(self, placeholder):
        self.set_context_settings(placeholder)
        if not placeholder.data.get("keep_placeholder", True):
            self.delete_placeholder(placeholder)

    def set_context_settings(self, placeholder):
        """Set context settings for the placeholder.

        Args:
            placeholder (dict): placeholder data
        """
        placeholder_context_data = {
            "resolution": placeholder.data.get("resolution", True),
            "frame_range": placeholder.data.get("frame_range", True),
            "colorspace": placeholder.data.get("colorspace", True),
            "scene_units": placeholder.data.get("scene_units", False),
        }
        set_context_settings(**placeholder_context_data)
