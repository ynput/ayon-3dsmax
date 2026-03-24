import os
from typing import List, Tuple, Any
from pathlib import Path
import pyblish.api

from pymxs import runtime as rt

from ayon_core.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_max.api.lib_rendersettings import (
    is_supported_renderer,
    RenderSettings,
)
from ayon_max.api.lib import (
    get_current_renderer,
    get_multipass_setting,
    get_vray_settings,
    is_redshift_default_output_regex_matched,
    is_general_default_output_regex_matched,
)

ARNOLD_DRIVERS = {
    "exr": rt.ArnoldEXRDriver,
    "png": rt.ArnoldPNGDriver,
    "jpg": rt.ArnoldJPEGDriver,
    "tif": rt.ArnoldTIFFDriver,
}

class ValidateRenderSettings(OptionalPyblishPluginMixin,
                             pyblish.api.InstancePlugin):
    """Validate render settings before render submission.

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
    label = "Validate Render Settings"
    actions = [RepairAction]

    settings_category = "max"

    def process(self, instance: pyblish.api.Instance) -> None:
        if not self.is_active(instance.data):
            return
        invalid = self.get_invalid(instance)
        if invalid:
            bullet_point_invalid_statement = "\n".join(
                f"- {err_type}: {filepath}" for err_type, filepath
                in invalid
            )
            report = (
                "Invalid render passes found.\n\n"
                f"{bullet_point_invalid_statement}\n\n"
                "You can use repair action to fix the invalid filepath."
            )
            raise PublishValidationError(
                report, title="Invalid Render Passes")

    @classmethod
    def _get_renderer_data(
        cls,
        instance: pyblish.api.Instance,
    ) -> Tuple[rt.Renderers.current, str]:
        """Return the active renderer object and its normalized name.

        Args:
            instance: Instance being validated.

        Returns:
            Active renderer object and renderer name.
        """
        renderer = get_current_renderer()
        renderer_name = instance.data.get("renderer")
        if not renderer_name:
            renderer_name = str(renderer).split(":")[0]
        return renderer, renderer_name

    @classmethod
    def get_invalid(
        cls,
        instance: pyblish.api.Instance,
    ) -> List[Tuple[str, str]]:
        """Collect invalid render settings for the current instance.

        Args:
            instance: Instance being validated.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        renderer, renderer_name = cls._get_renderer_data(instance)
        project_settings = instance.context.data["project_settings"]

        if is_supported_renderer(renderer_name):
            invalid.extend(
                cls.get_invalid_render_settings(instance, renderer_name)
            )

        if renderer_name.startswith("V_Ray_"):
            vr_settings = get_vray_settings(renderer_name)
            invalid.extend(
                cls.get_invalid_vray_settings(
                    instance, renderer_name, vr_settings, project_settings
                )
            )
        elif renderer_name == "Arnold":
            cls.log.warning(
                "Current validation for Arnold renderer only checks for "
                "the first AOV driver. Multiple drivers not supported yet."
            )
            invalid.extend(
                cls.get_invalid_arnold_settings(instance, renderer)
            )
        elif not is_supported_renderer(renderer_name):
            cls.log.debug(
                "Skipping render element validation for renderer: %s",
                renderer_name,
            )
        return invalid

    @classmethod
    def get_invalid_vray_filenames(
        cls,
        render_filename: str,
        extension: str,
    ) -> list[tuple[str, str]]:
        """Validate V-Ray output filenames.

        Args:
            render_filename: Render filename to validate.
            extension: Image format extension, for example `png` or
                `exr`.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        # ensure no double dot in the filename, e.g. John_Doe..exr
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
        filename: str,
        extension: str,
    ) -> list[tuple[str, str]]:
        """Validate a V-Ray output filename and handle empty values.

        Args:
            filename: Output filename from the renderer.
            extension: Expected file extension.

        Returns:
            Validation errors with details.
        """
        if not filename:
            message = "V-Ray output filename is empty. Please set it in render settings."
            cls.log.error(message)
            return [(message, filename)]

        return cls.get_invalid_vray_filenames(Path(filename).name, extension)

    @classmethod
    def get_invalid_vray_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        vr_settings: Any,
        project_settings: dict,
    ) -> list[tuple[str, str]]:
        """Validate V-Ray specific render settings.

        Args:
            instance: Instance being validated.
            renderer_name: Name of the renderer.
            vr_settings: V-Ray render settings object.
            project_settings: Project settings data.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        image_format = instance.data["imageFormat"]
        multipass_enabled = get_multipass_setting(renderer_name, project_settings)
        # check on multipass setting
        if multipass_enabled != vr_settings.output_splitgbuffer:
            invalid.append((
                "Invalid V-Ray multipass setting",
                f"Expected: {multipass_enabled}, "
                f"Found: {vr_settings.output_splitgbuffer}"
            ))

        if image_format == "exr":
            invalid_vray_outputs = cls._get_invalid_vray_output(
                vr_settings.output_rawfilename, image_format
            )
            invalid.extend(invalid_vray_outputs)

        if multipass_enabled:
            invalid_vray_outputs = cls._get_invalid_vray_output(
                vr_settings.output_splitfilename, image_format
            )
            invalid.extend(invalid_vray_outputs)
        else:
            invalid_outputs = cls.get_invalid_renderoutput(image_format)
            invalid.extend(invalid_outputs)

        return invalid

    @classmethod
    def get_invalid_renderoutput(
        cls,
        image_format: str,
    ) -> list[tuple[str, str]]:
        """Validate the beauty render output filename.

        Args:
            image_format: Expected image format for the render output.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        beauty_fname = os.path.basename(rt.rendOutputFilename)
        if not is_general_default_output_regex_matched(beauty_fname):
            invalid.append((
                "Invalid render output filename",
                "render output filename does not match the default output "
                f"regex, Found: {beauty_fname}"
            ))
        if not beauty_fname.endswith(f".{image_format}"):
            invalid.append((
                "Invalid render output filename",
                f"render output filename should end with .{image_format}, "
                f"Found: {beauty_fname}"
            ))
        return invalid

    @classmethod
    def get_invalid_render_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
    ) -> list[tuple[str, str]]:
        """Validate render output and render element filenames.

        Args:
            instance: Instance being validated.
            renderer_name: Name of the renderer.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        image_format = instance.data["imageFormat"]
        invalid.extend(cls.get_invalid_renderoutput(image_format))
        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        # If not render element has been added,
        # render element validation will be skipped.
        if render_elem_num < 1:
            return invalid

        for index in range(render_elem_num):
            renderlayer = render_elem.GetRenderElement(index)
            if renderlayer.enabled:
                r_fname = os.path.basename(render_elem.GetRenderElementFilename(index))
                if not cls._is_render_element_regex_matched(renderer_name, r_fname):
                    invalid.append((
                        "Invalid render element output filename",
                        "render element output filename does not match the "
                        f"default output regex, Found: {r_fname}"
                    ))
                if not r_fname.endswith(f".{image_format}"):
                    invalid.append((
                        "Invalid render element output filename",
                        f"render element output filename should end with "
                        f".{image_format}, Found: {r_fname}"
                    ))
        return invalid

    @classmethod
    def get_invalid_arnold_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer: rt.Renderers.current,
    ) -> list[tuple[str, str]]:
        """Validate Arnold-specific render settings.

        Args:
            instance: Instance being validated.
            renderer: Arnold renderer.

        Returns:
            Validation errors with their details.
        """
        invalid = []
        aov_drivers = renderer.AOVManager.drivers
        driver = aov_drivers[0]
        image_format = instance.data["imageFormat"]
        if rt.ClassOf(driver) != ARNOLD_DRIVERS.get(image_format):
            msg = (
                f"Invalid Arnold driver for image format {image_format}.\n"
                f"Should be: {ARNOLD_DRIVERS.get(image_format)}"
            )
            cls.log.error(msg)
            invalid.append((msg, driver))
        if not driver.filenameSuffix.endswith("."):
            invalid.append((
                "Invalid Arnold AOV driver filename",
                f"Arnold AOV driver filename suffix should end with '.', "
                f"Found: {driver.filenameSuffix}, "
                f"Should: {driver.filenameSuffix}."
            ))
        return invalid

    @classmethod
    def _is_render_element_regex_matched(
        cls,
        renderer_name: str,
        r_fname: str,
    ) -> bool:
        """Check if render element filename matches the renderer's output regex.

        Args:
            renderer_name: Renderer name.
            r_fname: Render element filename.

        Returns:
            True if filename matches the expected regex.
        """
        if renderer_name == "Redshift_Renderer":
            return (
                is_redshift_default_output_regex_matched(r_fname)
                or is_general_default_output_regex_matched(r_fname)
            )
        else:
            return is_general_default_output_regex_matched(r_fname)

    @classmethod
    def repair(cls, instance: pyblish.api.Instance) -> None:
        """Repair invalid render output filepaths.

        Args:
            instance: Instance being repaired.
        """
        renderer, renderer_name = cls._get_renderer_data(instance)
        if is_supported_renderer(renderer_name):
            cls.repair_general_render_settings(instance)
        if renderer_name.startswith("V_Ray_"):
            vr_settings = get_vray_settings(renderer_name)
            cls.repair_vray_settings(instance, renderer_name, vr_settings)
        if renderer_name == "Arnold":
            cls.repair_arnold_settings(instance, renderer)


    # Repair functions for specific renderers
    @classmethod
    def repair_general_render_settings(
        cls,
        instance: pyblish.api.Instance,
    ) -> None:
        """Repair invalid render output filepaths for general renderers.

        Args:
            instance: Instance being repaired.
        """
        image_format = instance.data["imageFormat"]
        renderer = instance.data["renderer"]
        renderoutput = rt.rendOutputFilename
        if not renderoutput:
            project_settings = instance.context.data["project_settings"]
            RenderSettings(project_settings).render_output(
                instance.data.get("instance_node")
            )
            renderoutput = rt.rendOutputFilename
        output_dir = os.path.dirname(renderoutput)
        filename = os.path.basename(renderoutput)
        if not is_general_default_output_regex_matched(filename):
            rt.rendOutputFilename = cls._build_general_output_filename(
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
        # If not render element has been added,
        # render element validation will be skipped.
        if render_elem_num < 1:
            return
        for index in range(render_elem_num):
            renderlayer = render_elem.GetRenderElement(index)
            if renderlayer.enabled:
                r_fname = os.path.basename(render_elem.GetRenderElementFilename(index))
                if not cls._is_render_element_regex_matched(renderer, r_fname):
                    output_filename = os.path.join(
                        os.path.dirname(render_elem.GetRenderElementFilename(index)),
                        cls._build_general_output_filename(
                            "", r_fname, image_format
                        )
                    )
                    render_elem.SetRenderElementFilename(index, output_filename)
                    cls.log.info(
                        "Render element output filename has been repaired to %s",
                        render_elem.GetRenderElementFilename(index),
                    )

    @classmethod
    def repair_vray_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer_name: str,
        vr_settings: Any,
    ) -> None:
        """Repair invalid V-Ray render output filepaths.

        Args:
            instance: Instance being repaired.
            renderer_name: Name of the renderer.
            vr_settings: V-Ray render settings object.
        """
        instance_node = instance.data.get("instance_node")
        image_format = instance.data["imageFormat"]
        project_settings = instance.context.data["project_settings"]
        multipass_enabled = get_multipass_setting(renderer_name, project_settings)
        vr_settings.output_splitgbuffer = multipass_enabled

        if image_format == "exr":
            vr_settings.output_rawfilename = cls._repair_vray_output_filename(
                vr_settings.output_rawfilename,
                image_format,
                instance_node,
                project_settings
            )
        else:
            vr_settings.output_splitfilename = cls._repair_vray_output_filename(
                vr_settings.output_splitfilename,
                image_format,
                instance_node,
                project_settings
            )

    @classmethod
    def _repair_vray_output_filename(
        cls,
        filename: str,
        image_format: str,
        instance_node: rt.Object,
        project_settings: dict,
    ) -> str:
        """Ensure a V-Ray output filename exists with the expected extension.

        Args:
            filename: Current output filename.
            image_format: Expected image format.
            instance_node: Instance node used by render settings.
            project_settings: Project settings data.

        Returns:
            Repaired V-Ray output filename.
        """
        if not filename:
            RenderSettings(project_settings).render_output(instance_node)
            filename = rt.rendOutputFilename

        output_dir = os.path.dirname(filename)
        output_filename = os.path.basename(filename)
        return cls._build_vray_output_filename(
            output_dir,
            output_filename,
            image_format,
        )

    @classmethod
    def _build_general_output_filename(
        cls,
        output_dir: str,
        filename: str,
        image_format: str,
    ) -> str:
        """Build a general output filename using double-dot style.

        Args:
            output_dir: Output directory.
            filename: Source filename.
            image_format: Expected image format.

        Returns:
            Rebuilt output filename.
        """
        name = os.path.splitext(filename)[0].rstrip(".").lstrip(".")
        output_filename = f"{name}..{image_format}"
        return os.path.join(output_dir, output_filename)

    @classmethod
    def _build_vray_output_filename(
        cls,
        output_dir: str,
        filename: str,
        image_format: str,
    ) -> str:
        """Build a V-Ray output filename using a single-dot extension.

        Args:
            output_dir: Output directory.
            filename: Source filename.
            image_format: Expected image format.

        Returns:
            Rebuilt V-Ray output filename.
        """
        name = os.path.splitext(filename)[0].lstrip(".")
        output_filename = f"{name}.{image_format}"
        return os.path.join(output_dir, output_filename)

    @classmethod
    def repair_arnold_settings(
        cls,
        instance: pyblish.api.Instance,
        renderer: rt.Renderers.current,
    ) -> None:
        """Repair invalid Arnold AOV driver settings.

        Args:
            instance: Instance being repaired.
            renderer: Arnold renderer.
        """
        image_format = instance.data["imageFormat"]
        aov_drivers = renderer.AOVManager.drivers
        driver = aov_drivers[0]
        if rt.ClassOf(driver) != ARNOLD_DRIVERS.get(image_format):
            driver_type = ARNOLD_DRIVERS.get(image_format)
            if driver_type:
                new_driver = driver_type()
                renderer.AOVManager.drivers[0] = new_driver
                driver = new_driver
                driver.filenameSuffix = f"{instance.name}."
                cls.log.info(
                    "Arnold AOV driver has been repaired to "
                    f"{new_driver} for image format {image_format}."
                )
            else:
                cls.log.warning(
                    f"No compatible Arnold driver found for image format {image_format}. "
                    "Please set the correct driver manually in render settings."
                )

        if not driver.filenameSuffix.endswith("."):
            driver.filenameSuffix = f"{driver.filenameSuffix}."
            cls.log.info(
                "Arnold AOV driver filename suffix has been repaired to "
                f"{driver.filenameSuffix}."
            )
