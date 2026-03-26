import os
from typing import Optional

import pyblish.api
from pymxs import runtime as rt

from ayon_core.pipeline.publish import (
    PublishValidationError,
    RepairAction,
    ValidateContentsOrder,
)
from ayon_max.api.lib import (
    get_current_renderer,
    get_multipass_setting,
    is_general_default_output_regex_matched,
    is_redshift_default_output_regex_matched,
    set_correct_workfile_name_for_render_output,
    build_general_output_filename

)
from ayon_max.api.lib_rendersettings import (
    RenderSettings,
    is_supported_renderer,
)


class ValidateGenericRenderSetting(pyblish.api.InstancePlugin):
    """Validate generic render settings before render submission.

    This validator ensures that render output filepaths and filenames
    are correctly configured for the current 3ds Max scene before submission
    to the render farm or local render. It validates the rendering settings
    across multiple supported renderers (V-Ray, Arnold, Redshift, and generic
    renderers) and provides automated repair capabilities.

    The plugin performs the following validation checks:

        1. Render Output Directory Structure
           Validates that the render output folder path matches the expected
           project hierarchy based on the current Max scene filename.
           e.g:
             Current Max scene: John_Doe.max
             Expected output directory:
               {root[work]}/{project[name]}/{hierarchy}/{asset}/
               work/{task[name]}/render/3dsmax/John_Doe/

        2. Image File Extension Compliance
           Ensures that all render output files use the correct image format
           extension as defined in the AYON project settings.
           e.g:
             Configured format in AYON: png
             Expected render outputs: John_Doe.png (and all render elements)
             Invalid outputs: John_Doe.jpg or John_Doe.exr (if format is png)

        3. Render Element Filename Validation
           Checks that each render element output filename follows the naming
           convention and ends with the render element's identifier from the
           3ds Max Render Element Manager.
           e.g.
             Render element name: RsCryptomatte
             Expected filename format: {InstanceName}_RsCryptomatte.png

    The plugin includes repair actions that can fix common naming
    and configuration issues, making it easier for artists to comply with
    project naming conventions without manual intervention.
    """

    order = ValidateContentsOrder
    families = ["maxrender", "renderpreset"]
    hosts = ["max"]
    label = "Validate Generic Render Setting"
    actions = [RepairAction]

    settings_category = "max"

    def process(self, instance: pyblish.api.Instance) -> None:
        """Process the instance to validate generic render settings.

        Args:
            instance (pyblish.api.Instance): The instance to validate.

        Raises:
            PublishValidationError: If any invalid render settings are found.
        """
        if not self.is_active(instance.data):
            return

        renderer, renderer_name = self._get_renderer_data(instance)
        if not self._matches_renderer_name(renderer_name):
            return

        invalid = self._get_invalid_settings(instance, renderer, renderer_name)
        if invalid:
            bullet_point_invalid_statement = "\n".join(
                f"- {err_type}: {filepath}" for err_type, filepath in invalid
            )
            report = (
                "Invalid render passes found.\n\n"
                f"{bullet_point_invalid_statement}\n\n"
                "You can use repair action to fix the invalid filepath."
            )
            raise PublishValidationError(
                report,
                title="Invalid Render Passes",
            )

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
            cls.log.error(msg)
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

    @classmethod
    def get_invalid_render_element_directory(
        cls,
        directory: str,
        workfile_pattern: str,
        multi_camera: bool = False,
        cameras: Optional[list[str]] = None,
    ) -> list[tuple[str, str]]:
        """Get the invalid render element directory settings.

        Args:
            directory (str): render directory to validate
            workfile_pattern (str): workfile name pattern to validate
            multi_camera (bool, optional): Whether multi-camera is enabled.
            Defaults to False.
            cameras (Optional[list[str]], optional): The list of camera
                names to validate. Defaults to None.

        Returns:
            list[tuple[str, str]]: A list of tuples containing the error
                type and the invalid directory.
        """
        invalid = []
        if workfile_pattern not in directory:
            msg = (
                f"Invalid render element output directory {directory}. "
                f"Directory should contain the workfile name pattern: {workfile_pattern}."
            )
            cls.log.error(msg)
            invalid.append((msg, directory))

        if multi_camera and cameras:
            for camera in cameras:
                if camera not in directory:
                    invalid.append((
                        "Invalid render element output directory",
                        "Render element output directory should contain camera name "
                        f"{camera} when multiCamera is enabled. Found: {directory}",
                    ))

        return invalid

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
        invalid = []
        image_format = instance.data["imageFormat"]
        if renderer_name == "Redshift_Renderer":
            multipass_enabled = get_multipass_setting(
                renderer_name,
                project_settings,
            )
            if renderer.separateAovFiles != multipass_enabled:
                invalid.append((
                    "Invalid Redshift multipass setting",
                    f"Expected: {multipass_enabled}, Found: {renderer.separateAovFiles}",
                ))

        multicam = instance.data.get("multiCamera", False)
        cameras = instance.data.get("cameras", [])
        invalid.extend(
            cls.get_invalid_renderoutput(
                image_format,
                workfile_pattern,
                multicam=multicam,
                cameras=cameras,
            )
        )

        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        if render_elem_num < 1:
            return invalid

        for index in range(render_elem_num):
            renderlayer = render_elem.GetRenderElement(index)
            if not renderlayer.enabled:
                continue

            render_element_filename = render_elem.GetRenderElementFilename(index)
            invalid.extend(
                cls.get_invalid_render_element_directory(
                    os.path.dirname(render_element_filename),
                    workfile_pattern,
                    multi_camera=multicam,
                    cameras=cameras,
                )
            )
            r_fname = os.path.basename(render_element_filename)
            if not cls._is_render_element_regex_matched(renderer_name, r_fname):
                invalid.append((
                    "Invalid render element output filename",
                    "render element output filename does not match the "
                    f"default output regex, Found: {r_fname}",
                ))
            if not r_fname.endswith(f".{image_format}"):
                invalid.append((
                    "Invalid render element output filename",
                    "render element output filename should end with "
                    f".{image_format}, Found: {r_fname}",
                ))
        return invalid

    @classmethod
    def _is_render_element_regex_matched(
        cls,
        renderer_name: str,
        render_element_filename: str,
    ) -> bool:
        """Check if the render element filename matches the default output regex.

        Args:
            renderer_name (str): The name of the renderer.
            render_element_filename (str): The render element filename to check.

        Returns:
            bool: True if the filename matches the default output regex, False otherwise.
        """

        if renderer_name == "Redshift_Renderer":
            return (
                is_redshift_default_output_regex_matched(render_element_filename)
                or is_general_default_output_regex_matched(render_element_filename)
            )
        return is_general_default_output_regex_matched(render_element_filename)

    @classmethod
    def repair(cls, instance: pyblish.api.Instance) -> None:
        renderer, renderer_name = cls._get_renderer_data(instance)
        if not cls._matches_renderer_name(renderer_name):
            return

        if instance.data.get("multiCamera"):
            instance_node = instance.data.get("instance_node")
            project_settings = instance.context.data["project_settings"]
            RenderSettings(project_settings).render_output(instance_node)
            return

        cls.repair_generic_render_settings(instance, renderer_name, renderer)

    @classmethod
    def repair_generic_render_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        renderer: rt.Renderers.current,
    ) -> None:
        """Repair the generic render settings.

        Args:
            instance (pyblish.api.Instance): The instance to repair.
            renderer_name (str): The name of the renderer.
            renderer (rt.Renderers.current): The current renderer.
        """
        image_format = instance.data["imageFormat"]
        renderoutput = rt.rendOutputFilename
        project_settings = instance.context.data["project_settings"]
        if not renderoutput:
            RenderSettings(project_settings).render_output(
                instance.data.get("instance_node")
            )
            renderoutput = rt.rendOutputFilename

        output_dir = set_correct_workfile_name_for_render_output(
            instance,
            os.path.dirname(renderoutput),
        )
        if renderer_name == "Redshift_Renderer":
            renderer.separateAovFiles = get_multipass_setting(
                renderer_name,
                project_settings,
            )

        filename = os.path.basename(renderoutput)
        if not is_general_default_output_regex_matched(filename):
            rt.rendOutputFilename = build_general_output_filename(
                output_dir,
                filename,
                image_format,
            )
            cls.log.info(
                "Render output filename has been repaired to %s",
                rt.rendOutputFilename,
            )
        else:
            cls.log.info("Render output filename is correct. No need to repair.")

        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        if render_elem_num < 1:
            return

        for index in range(render_elem_num):
            renderlayer = render_elem.GetRenderElement(index)
            if not renderlayer.enabled:
                continue

            render_element_filename = render_elem.GetRenderElementFilename(index)
            r_fname = os.path.basename(render_element_filename)
            if not cls._is_render_element_regex_matched(renderer_name, r_fname):
                output_filename = os.path.join(
                    os.path.dirname(render_element_filename),
                    build_general_output_filename("", r_fname, image_format),
                )
                render_elem.SetRenderElementFilename(index, output_filename)
                cls.log.info(
                    "Render element output filename has been repaired to %s",
                    render_elem.GetRenderElementFilename(index),
                )
