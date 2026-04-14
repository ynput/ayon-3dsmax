import os
from typing import Optional

import pyblish.api
from pymxs import runtime as rt


from ayon_max.api.lib import (
    get_current_renderer,
    is_general_default_output_regex_matched,

)
from ayon_max.api.lib_rendersettings import is_supported_renderer


class ValidateRenderSettingsBase(object):
    """Base helper for validating renderer-specific publish settings.

    This class provides shared utilities to resolve renderer/context data and
    validate common render output naming rules. Subclasses are expected to
    implement `_get_invalid_settings` with renderer-specific validation logic.
    """

    @classmethod
    def _get_renderer_data(
        cls,
        instance: pyblish.api.Instance,
    ) -> tuple[rt.Renderers.current, str]:
        """Get the renderer data for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to get renderer data for.

        Returns:
            tuple[rt.Renderers.current, str]: The current renderer and its name.
        """
        renderer = get_current_renderer()
        renderer_name = instance.data.get("renderer")
        if not renderer_name:
            renderer_name = str(renderer).split(":")[0]
        return renderer, renderer_name

    @classmethod
    def _get_validation_context(
        cls,
        instance: pyblish.api.Instance,
    ) -> tuple[dict, str]:
        """Get project settings and workfile pattern for validation.

        Args:
            instance (pyblish.api.Instance): The instance to get validation context for.

        Returns:
            tuple[dict, str]: The project settings and workfile pattern.
        """
        project_settings = instance.context.data["project_settings"]
        current_file = instance.context.data["currentFile"]
        workfile_pattern = os.path.splitext(
            os.path.basename(current_file)
        )[0].strip(".")
        return project_settings, workfile_pattern

    @classmethod
    def _matches_renderer_name(cls, renderer_name: str) -> bool:
        """Check if the renderer name matches the supported renderers.

        Args:
            renderer_name (str): The name of the renderer to check.

        Returns:
            bool: True if the renderer is supported, False otherwise.
        """
        return is_supported_renderer(renderer_name)

    @classmethod
    def _get_invalid_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer: rt.Renderers.current,
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

        return cls.get_invalid_render_settings(
                instance,
                renderer_name,
                workfile_pattern,
                renderer,
                project_settings,
        )

    @classmethod
    def get_invalid_render_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        workfile_pattern: str,
        renderer: rt.Renderers.current,
        project_settings: dict,
    ) -> list[tuple[str, str]]:
        """Get the invalid render settings.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer_name (str): The name of the renderer.
            workfile_pattern (str): The workfile name pattern to validate.
            renderer (rt.Renderers.current): The current renderer.
            project_settings (dict): The project settings.

        Returns:
            list[tuple[str, str]]: A list of tuples containing the error
                type and the invalid setting.
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @classmethod
    def get_invalid_renderoutput(
        cls,
        image_format: str,
        workfile_pattern: str,
        multicam: bool = False,
        cameras: Optional[list[str]] = None,
    ) -> list[tuple[str, str]]:
        """Get the invalid render output settings.

        Args:
            image_format (str): The image format to validate.
            workfile_pattern (str): The workfile pattern to validate.
            multicam (bool, optional): Whether multi-camera is enabled.
                Defaults to False.
            cameras (Optional[list[str]], optional): The list of camera names
                to validate. Defaults to None.

        Returns:
            list[tuple[str, str]]: A list of tuples containing the error type
                and the invalid filepath.
        """
        invalid = []
        beauty_dir = os.path.dirname(rt.rendOutputFilename)
        if workfile_pattern not in beauty_dir:
            msg = (
                f"Invalid render output filename {rt.rendOutputFilename}. "
                f"Filename should contain the workfile name pattern: {workfile_pattern}."
            )
            invalid.append((msg, beauty_dir))

        beauty_fname = os.path.basename(rt.rendOutputFilename)
        if multicam and cameras:
            for camera in cameras:
                if camera not in beauty_fname:
                    invalid.append((
                        "Invalid render output filename",
                        "Render output filename should contain camera name "
                        f"{camera} when multiCamera is enabled. Found: {beauty_fname}",
                    ))

        if not is_general_default_output_regex_matched(beauty_fname):
            invalid.append((
                "Invalid render output filename",
                "render output filename does not match the default output "
                f"regex, Found: {beauty_fname}",
            ))

        if not beauty_fname.endswith(f".{image_format}"):
            invalid.append((
                "Invalid render output filename",
                f"render output filename should end with .{image_format}, "
                f"Found: {beauty_fname}",
            ))
        return invalid
