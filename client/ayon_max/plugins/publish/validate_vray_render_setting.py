import os
from typing import Any

import pyblish.api
from pymxs import runtime as rt

from ayon_max.api.lib import (
    get_multipass_setting,
    get_vray_settings,
    set_correct_workfile_name_for_render_output
)
from ayon_max.api.lib_rendersettings import RenderSettings
from ayon_max.plugins.publish.validate_generic_render_setting import (
    ValidateGenericRenderSetting
)


class ValidateVrayRenderSetting(ValidateGenericRenderSetting):
    """Validate V-Ray render settings before render submission.

     This validator extends the generic render setting validation with
     V-Ray-specific checks. It keeps the shared validation inherited from
     :class:`ValidateGenericRenderSetting`, such as validating the beauty
     output path, render element output directories, file naming patterns,
     and image extension consistency, and adds checks for the V-Ray output
     configuration that is required for AYON publishing.

     The plugin performs the following V-Ray-specific validation checks:

          1. V-Ray Multipass Configuration
              Validates that ``output_splitgbuffer`` matches the multipass
              expectation from the AYON project settings.

          2. Raw Output Filename Validation
              When the configured image format is ``exr``, validates that the
              V-Ray raw output filename is defined, points to the expected
              workfile-based output directory, and uses the expected extension.

          3. Split Channel Output Validation
              When multipass rendering is enabled, validates that the split
              output filename is configured correctly and follows the expected
              naming pattern for the current scene.

          4. Beauty Output Fallback Validation
              When multipass rendering is disabled, falls back to validating the
              standard beauty output path using the shared generic validation.

     The repair action updates the V-Ray output configuration to match the
     project settings and rebuilds invalid output filenames so artists can
     fix common publish issues directly from the validator.

    """

    label = "Validate Vray Render Setting"

    @classmethod
    def _matches_renderer_name(cls, renderer_name: str) -> bool:
        """Check if the renderer name matches the supported renderers.

        Args:
            renderer_name (str): The name of the renderer to check.

        Returns:
            bool: True if the renderer is supported, False otherwise.
        """
        return renderer_name.startswith("V_Ray_")

    @classmethod
    def _get_invalid_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer,
        renderer_name: str,
    ) -> list[tuple[str, str]]:
        """Get invalid V-Ray settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer (_type_): The renderer object.
            renderer_name (str): The name of the renderer.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error
              messages and invalid values.
        """
        _, _, project_settings, workfile_pattern = cls._get_validation_context(
            instance
        )
        vr_settings = get_vray_settings(renderer_name, renderer)
        return cls.get_invalid_vray_settings(
                instance,
                renderer_name,
                workfile_pattern,
                vr_settings,
                project_settings,
            )

    @classmethod
    def get_invalid_vray_filepaths(
        cls,
        render_filepath: str,
        extension: str,
        workfile_pattern: str,
    ) -> list[tuple[str, str]]:
        """Get invalid V-Ray filepaths for the given instance.

        Args:
            render_filepath (str): The render output filepath.
            extension (str): The expected file extension.
            workfile_pattern (str): The workfile name pattern.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error messages and invalid values.
        """
        invalid = []
        render_dir = os.path.dirname(render_filepath)
        render_filename = os.path.basename(render_filepath)
        if workfile_pattern not in render_dir:
            msg = (
                f"Invalid render output filename {render_filename} for V-Ray. "
                f"Filename should contain the workfile name pattern: {workfile_pattern}."
            )
            cls.log.error(msg)
            invalid.append((msg, render_dir))
        if ".." in render_filename:
            msg = (
                f"Invalid render output filename {render_filename} for V-Ray "
                "Filename should not contain double dots."
            )
            cls.log.error(msg)
            invalid.append((msg, render_filename))
        if not render_filename.endswith(f".{extension}"):
            msg = (
                f"Invalid render output filename {render_filename} for V-Ray "
                f"Filename should end with .{extension}."
            )
            cls.log.error(msg)
            invalid.append((msg, render_filename))

        return invalid

    @classmethod
    def _get_invalid_vray_output(
        cls,
        filepath: str,
        extension: str,
        workfile_pattern: str,
    ) -> list[tuple[str, str]]:
        """Get invalid V-Ray output settings for the given instance.

        Args:
            filepath (str): The render output filepath.
            extension (str): The expected file extension.
            workfile_pattern (str): The workfile name pattern.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error
                messages and invalid values.
        """
        if not filepath:
            message = (
                "V-Ray output filepath is empty. "
                "Please set it in render settings."
            )
            cls.log.error(message)
            return [(message, filepath)]

        return cls.get_invalid_vray_filepaths(
            filepath,
            extension,
            workfile_pattern,
        )

    @classmethod
    def get_invalid_vray_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        workfile_pattern: str,
        vr_settings: Any,
        project_settings: dict,
    ) -> list[tuple[str, str]]:
        """Get invalid V-Ray settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer_name (str): The name of the renderer.
            workfile_pattern (str): The workfile name pattern.
            vr_settings (Any): The V-Ray settings object.
            project_settings (dict): The project settings dictionary.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error messages
                and invalid values.
        """
        invalid = []
        image_format = instance.data["imageFormat"]
        multipass_enabled = get_multipass_setting(renderer_name, project_settings)
        if multipass_enabled != vr_settings.output_splitgbuffer:
            invalid.append((
                "Invalid V-Ray multipass setting",
                f"Expected: {multipass_enabled}, Found: {vr_settings.output_splitgbuffer}",
            ))

        if image_format == "exr":
            invalid.extend(
                cls._get_invalid_vray_output(
                    vr_settings.output_rawfilename,
                    image_format,
                    workfile_pattern,
                )
            )

        if multipass_enabled:
            invalid.extend(
                cls._get_invalid_vray_output(
                    vr_settings.output_splitfilename,
                    image_format,
                    workfile_pattern,
                )
            )
        else:
            invalid.extend(
                cls.get_invalid_renderoutput(image_format, workfile_pattern)
            )

        return invalid

    @classmethod
    def repair(cls, instance: pyblish.api.Instance) -> None:
        """Repair invalid V-Ray render settings for the given instance.

        Args:
            instance (pyblish.api.Instance): instance to repair
        """
        renderer, renderer_name = cls._get_renderer_data(instance)
        if not cls._matches_renderer_name(renderer_name):
            return
        vr_settings = get_vray_settings(renderer_name, renderer)
        cls.repair_vray_settings(
            instance,
            renderer_name,
            vr_settings,
        )

    @classmethod
    def repair_vray_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        vr_settings: Any,
    ) -> None:
        """Repair V-Ray settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to repair.
            renderer_name (str): The name of the renderer.
            vr_settings (Any): The V-Ray settings object.
        """
        image_format = instance.data["imageFormat"]
        project_settings = instance.context.data["project_settings"]
        multipass_enabled = get_multipass_setting(renderer_name, project_settings)
        vr_settings.output_splitgbuffer = multipass_enabled

        if image_format == "exr":
            vr_settings.output_rawfilename = cls._repair_vray_output_filename(
                vr_settings.output_rawfilename,
                image_format,
                instance,
            )
            return

        vr_settings.output_splitfilename = cls._repair_vray_output_filename(
            vr_settings.output_splitfilename,
            image_format,
            instance,
        )

    @classmethod
    def _repair_vray_output_filename(
        cls,
        filename: str,
        image_format: str,
        instance: pyblish.api.Instance,
    ) -> str:
        """Repair the V-Ray output filename for the given instance.

        Args:
            filename (str): The current V-Ray output filename.
            image_format (str): The image format for the output file.
            instance (pyblish.api.Instance): The instance being processed.

        Returns:
            str: The repaired V-Ray output filename.
        """
        instance_node = instance.data.get("instance_node")
        project_settings = instance.context.data["project_settings"]
        if not filename:
            RenderSettings(project_settings).render_output(instance_node)
            filename = rt.rendOutputFilename

        output_dir = set_correct_workfile_name_for_render_output(
            instance,
            os.path.dirname(filename),
        )
        output_filename = os.path.basename(filename)
        return cls._build_vray_output_filename(
            output_dir,
            output_filename,
            image_format,
        )

    @classmethod
    def _build_vray_output_filename(
        cls,
        output_dir: str,
        filename: str,
        image_format: str,
    ) -> str:
        """Build the full path for the V-Ray output file.

        Args:
            output_dir (str): The directory where the output file will be saved.
            filename (str): The name of the output file.
            image_format (str): The image format for the output file.

        Returns:
            str: The full path to the repaired V-Ray output file.
        """
        name = os.path.splitext(filename)[0].lstrip(".")
        output_filename = f"{name}.{image_format}"
        return os.path.join(output_dir, output_filename)