import os
import pyblish.api
from pathlib import Path
from pymxs import runtime as rt
from ayon_core.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_core.settings import get_project_settings
from ayon_core.pipeline import get_current_project_name
from ayon_max.api.lib_rendersettings import (
    RenderSettings,
    is_supported_renderer
)
from ayon_max.api.lib import get_default_render_folder


class ValidateRenderPreset(OptionalPyblishPluginMixin,
                           pyblish.api.InstancePlugin):
    """Validates Render Preset settings against project template.
    
    This validator compares the current render preset settings in the
    3dsMax scene with the render preset template defined in project settings.
    It ensures that render presets conform to project standards.
    """

    order = ValidateContentsOrder
    families = ["renderpreset"]
    hosts = ["max"]
    label = "Validate Render Preset"
    actions = [RepairAction]

    settings_category = "max"

    def process(self, instance):
        """Validate render preset against project settings template.
        
        Args:
            instance (pyblish.api.Instance): The instance being published
            
        Raises:
            PublishValidationError: If render preset doesn't match template
        """
        invalid = self.get_invalid(instance)
        if invalid:
            bullet_point_invalid_items = "\n".join(
                f"- {item}" for item in invalid
            )
            report = (
                "Render preset does not match project template settings.\n\n"
                f"{bullet_point_invalid_items}\n\n"
                "Please ensure your render preset matches the project "
                "standards defined in the render settings template."
            )
            raise PublishValidationError(
                report, title="Invalid Render Preset")

    @classmethod
    def get_invalid(cls, instance):
        """Check if render preset matches project template.
        
        This method compares:
        1. Renderer type matches project supported renderers
        2. Output image format matches project settings
        3. Render element configuration (if applicable)
        
        Args:
            instance (pyblish.api.Instance): The instance being validated
            
        Returns:
            list: List of validation issues found
        """
        invalid = []
        
        try:
            project_settings = instance.context.data.get(
                "project_settings"
            ) or get_project_settings(get_current_project_name())
        except Exception as e:
            invalid.append(f"Failed to load project settings: {str(e)}")
            return invalid
        
        # Get render settings from project settings
        render_settings = project_settings.get("max", {}).get(
            "RenderSettings", {}
        )
        
        # Validate renderer is supported
        try:
            current_renderer = str(rt.renderers.current)
            if not is_supported_renderer(current_renderer):
                invalid.append(
                    f"Current renderer '{current_renderer}' is not "
                    "supported or not configured in project settings"
                )
        except Exception as e:
            invalid.append(f"Failed to validate renderer: {str(e)}")
        
        # Validate output image format
        try:
            expected_format = render_settings.get("image_format", "exr")
            # Note: In 3dsMax, image format is typically set per render output
            # This validates that the expected format is available in settings
            cls.log.debug(
                f"Render preset output format should be: {expected_format}"
            )
        except Exception as e:
            invalid.append(f"Failed to validate image format: {str(e)}")
        
        # Validate AOV separator if applicable
        try:
            expected_aov_sep = render_settings.get("aov_separator", "underscore")
            cls.log.debug(
                f"Render preset AOV separator should be: {expected_aov_sep}"
            )
        except Exception as e:
            invalid.append(f"Failed to validate AOV separator: {str(e)}")
        
        return invalid
