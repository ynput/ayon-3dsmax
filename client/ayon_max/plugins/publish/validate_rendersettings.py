import os
from typing import Optional, Any

import pyblish.api
from pymxs import runtime as rt

from ayon_core.pipeline.publish import (
    PublishValidationError,
    RepairAction,
    ValidateContentsOrder,
)
from ayon_max.api.lib import (
    get_multipass_setting,
    is_general_default_output_regex_matched,
    set_correct_workfile_name_for_render_output,
    build_general_output_filename,
    get_vray_settings

)
from ayon_max.api.validate_plugins import ValidateRenderSettingsBase
from ayon_max.api.lib_rendersettings import (
    RenderSettings,
    get_arnold_driver_for_image_format,
)



class ValidateGenericRenderSetting(pyblish.api.InstancePlugin,
                                   ValidateRenderSettingsBase):
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
            if image_format == "exr" and not renderer.OutputExrMultipart:
                invalid.append((
                    "Invalid Redshift render setting",
                    "EXR image format should have OutputExrMultipart enabled for AOVs.",
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
            if not is_general_default_output_regex_matched(r_fname):
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
            if image_format == "exr":
                renderer.OutputExrMultipart = get_multipass_setting(
                    renderer_name,
                    project_settings,
                )

        filename = os.path.basename(renderoutput)
        rt.rendOutputFilename = build_general_output_filename(
            output_dir,
            filename,
            image_format,
        )
        cls.log.info(
            "Render output filename has been repaired to %s",
            rt.rendOutputFilename,
        )

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
            output_dir = set_correct_workfile_name_for_render_output(
                instance,
                os.path.dirname(render_element_filename),
            )
            output_filename = build_general_output_filename(
                output_dir, r_fname, image_format
            )
            render_elem.SetRenderElementFilename(index, output_filename)
            cls.log.info(
                "Render element output filename has been repaired to %s",
                render_elem.GetRenderElementFilename(index),
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
    def get_invalid_render_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        workfile_pattern: str,
        renderer: rt.Renderers.current,
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
        image_format = instance.data["imageFormat"]
        invalid.extend(
            cls.get_invalid_renderoutput(
            image_format,
            workfile_pattern
        ))
        if workfile_pattern not in output_path:
            msg = (
                f"Invalid Arnold AOV output path {output_path}. "
                f"Output path should contain the workfile name pattern: {workfile_pattern}."
            )
            cls.log.error(msg)
            invalid.append((msg, output_path))

        aov_drivers = aov_manager.drivers
        driver = aov_drivers[0]
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
        # check if the beauty output path is correct if using the
        # default native 3dsmax render
        render_output = rt.rendOutputFilename
        render_dir = set_correct_workfile_name_for_render_output(
            instance,
            os.path.dirname(render_output),
        )
        filename = os.path.basename(render_output)
        rt.rendOutputFilename = build_general_output_filename(
            render_dir,
            filename,
            image_format,
        )
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
    def get_invalid_render_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        workfile_pattern: str,
        renderer: rt.Renderers.current,
        project_settings: dict,
    ) -> list[tuple[str, str]]:
        """Get invalid V-Ray settings for the given instance.

        Args:
            instance (pyblish.api.Instance): The instance to validate.
            renderer_name (str): The name of the renderer.
            workfile_pattern (str): The workfile name pattern.
            renderer (rt.Renderers.current): The current renderer.
            project_settings (dict): The project settings dictionary.

        Returns:
            list[tuple[str, str]]: A list of tuples containing error messages
                and invalid values.
        """
        invalid = []
        vr_settings = get_vray_settings(renderer_name, renderer)
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
        if multipass_enabled:
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
