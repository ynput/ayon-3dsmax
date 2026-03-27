import pyblish.api
from pymxs import runtime as rt

from ayon_max.api.lib import (
    get_multipass_setting,
    set_correct_workfile_name_for_render_output
)
from ayon_max.api.lib_rendersettings import get_arnold_driver_for_image_format
from ayon_max.plugins.publish.validate_generic_render_setting import (
    ValidateGenericRenderSetting
)


class ValidateArnoldRenderSetting(ValidateGenericRenderSetting):
    """Validate Arnold render settings before render submission.

     This validator extends the generic render setting validation with
     Arnold-specific checks. It keeps the shared validation inherited from
     :class:`ValidateGenericRenderSetting`, such as validating the beauty
     output path, render element output directories, filename patterns, and
     image extension consistency, and adds validation for Arnold AOV output
     configuration required by the publish pipeline.

     The plugin performs the following Arnold-specific validation checks:

          1. Arnold AOV Output Path Validation
              Validates that the Arnold AOV output path points to the expected
              workfile-based render directory for the current scene.

          2. Arnold Driver Type Validation
              Ensures that the first Arnold AOV driver matches the expected
              driver type for the configured AYON image format.

          3. Arnold Multipart Configuration
              Validates that Arnold multipart output matches the multipass
              expectation from the AYON project settings.

          4. Arnold Driver Filename Suffix Validation
              Checks that the Arnold AOV driver filename suffix ends with a dot,
              which is required for correct output filename generation.

     The repair action updates the Arnold AOV output path, configures the
     expected multipart state, replaces an invalid driver type when possible,
     and fixes the filename suffix so common publish issues can be repaired
     directly from the validator.

     Note:
          The current implementation validates only the first Arnold AOV driver.
          Multiple drivers are not supported by this validator yet.
    """

    label = "Validate Arnold Render Setting"

    @classmethod
    def _matches_renderer_name(cls, renderer_name: str) -> bool:
        """Check if the renderer name matches the supported renderers.

        Args:
            renderer_name (str): The name of the renderer to check.

        Returns:
            bool: True if the renderer is supported, False otherwise.
        """
        return renderer_name == "Arnold"

    @classmethod
    def _get_invalid_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer,
        renderer_name: str,
    ) -> list[tuple[str, str]]:
        """Get the invalid render settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer (rt.Renderers.current): The current renderer.
            renderer_name (str): The name of the renderer.


        Returns:
            list[tuple[str, str]]: invalid render settings as a list of tuples
                containing the error type and the invalid filepath.
        """
        project_settings, workfile_pattern = cls._get_validation_context(
            instance
        )
        cls.log.warning(
            "Current validation for Arnold renderer only checks for "
            "the first AOV driver. Multiple drivers not supported yet."
        )
        return cls.get_invalid_arnold_settings(
                instance,
                renderer,
                renderer_name,
                workfile_pattern,
                project_settings,
        )

    @classmethod
    def get_invalid_arnold_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer: rt.Renderers.current,
        renderer_name: str,
        workfile_pattern: str,
        project_settings: dict,
    ) -> list[tuple[str, str]]:
        """Get invalid Arnold settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer (rt.Renderers.current): The current renderer.
            renderer_name (str): The name of the renderer.
            workfile_pattern (str): The workfile name pattern.
            project_settings (dict): The project settings dictionary.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error messages
                and invalid values.
        """
        invalid = []
        aov_manager = renderer.AOVManager
        output_path = aov_manager.outputPath
        if workfile_pattern not in output_path:
            msg = (
                f"Invalid Arnold AOV output path {output_path}. "
                f"Output path should contain the workfile name pattern: {workfile_pattern}."
            )
            cls.log.error(msg)
            invalid.append((msg, output_path))

        aov_drivers = aov_manager.drivers
        driver = aov_drivers[0]
        image_format = instance.data["imageFormat"]
        arnold_driver = get_arnold_driver_for_image_format(image_format)
        if rt.ClassOf(driver) != arnold_driver:
            msg = (
                f"Invalid Arnold driver for image format {image_format}.\n"
                f"Should be: {arnold_driver}"
            )
            cls.log.error(msg)
            invalid.append((msg, driver))

        multipass_enabled = get_multipass_setting(renderer_name, project_settings)
        if driver.multipart != multipass_enabled:
            invalid.append((
                "Invalid Arnold multipass setting",
                f"Expected: {multipass_enabled}, Found: {driver.multipart}",
            ))
        if not driver.filenameSuffix.endswith("."):
            invalid.append((
                "Invalid Arnold AOV driver filename",
                "Arnold AOV driver filename suffix should end with '.', "
                f"Found: {driver.filenameSuffix}.",
            ))
        return invalid

    @classmethod
    def repair(cls, instance: pyblish.api.Instance) -> None:
        """Repair invalid Arnold render settings for the given instance.

        Args:
            instance (pyblish.api.Instance): Instance to repair.
        """
        renderer, renderer_name = cls._get_renderer_data(instance)
        if not cls._matches_renderer_name(renderer_name):
            return

        cls.repair_arnold_settings(instance, renderer, renderer_name)

    @classmethod
    def repair_arnold_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer: rt.Renderers.current,
        renderer_name: str,
    ) -> None:
        """Repair invalid Arnold settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to repair.
            renderer (rt.Renderers.current): The current renderer.
            renderer_name (str): The name of the renderer.
        """
        image_format = instance.data["imageFormat"]
        project_settings = instance.context.data["project_settings"]
        aov_manager = renderer.AOVManager
        path = set_correct_workfile_name_for_render_output(
            instance,
            aov_manager.outputPath,
        )
        aov_manager.outputPath = path
        driver = aov_manager.drivers[0]
        driver.multipart = get_multipass_setting(
            renderer_name,
            project_settings,
        )
        arnold_driver = get_arnold_driver_for_image_format(image_format)
        if rt.ClassOf(driver) != arnold_driver:
            driver_type = arnold_driver
            if driver_type:
                new_driver = driver_type()
                aov_manager.drivers[0] = new_driver
                driver = new_driver
                driver.filenameSuffix = f"{instance.name}."
                cls.log.info(
                    "Arnold AOV driver has been repaired to %s for image format %s.",
                    new_driver,
                    image_format,
                )
            else:
                cls.log.warning(
                    "No compatible Arnold driver found for image format %s. "
                    "Please set the correct driver manually in render settings.",
                    image_format,
                )

        if not driver.filenameSuffix.endswith("."):
            driver.filenameSuffix = f"{driver.filenameSuffix}."
            cls.log.info(
                "Arnold AOV driver filename suffix has been repaired to %s.",
                driver.filenameSuffix,
            )
