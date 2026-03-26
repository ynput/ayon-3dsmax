# Render Element Example : For scanline render, VRay
# https://help.autodesk.com/view/MAXDEV/2022/ENU/?guid=GUID-E8F75D47-B998-4800-A3A5-610E22913CFC
# arnold
# https://help.autodesk.com/view/ARNOL/ENU/?guid=arnold_for_3ds_max_ax_maxscript_commands_ax_renderview_commands_html
from __future__ import annotations
import os
from typing import Dict, Any

try:
    from pymxs import runtime as rt

except ImportError:
    rt = None


from ayon_max.api.lib import (
    get_current_renderer,
    get_multipass_setting,
    reformat_filename,
)
from ayon_core.pipeline import get_current_project_name
from ayon_core.settings import get_project_settings
from ayon_max.api.lib_rendersettings import is_supported_renderer


class RenderProducts(object):
    """Class for managing render products in 3ds Max."""
    def __init__(self, project_settings: Dict[str, Any] = None):
        """Initialize the RenderProducts class.

        Args:
            project_settings (Dict[str, Any], optional): Project settings
                dictionary. Defaults to None.
        """
        self._project_settings = project_settings
        if not self._project_settings:
            self._project_settings = get_project_settings(
                get_current_project_name()
            )

    def get_render_products(self) -> Dict[str, list[str]]:
        """Get render output file paths for the current scene.

        Handles both beauty and AOV extraction with shared setup logic.
        Always includes the beauty pass; optionally includes render elements/AOVs.

        Returns:
            Dict[str, list[str]]: A dictionary containing render output file paths.
                Beauty key is "beauty"; AOV keys are named after the render element
                (e.g., "Cryptomatte", "Alpha").
        """
        extension = self.image_format()
        start_frame = int(rt.rendStart)
        end_frame = int(rt.rendEnd) + 1
        # todo: Support Custom Frames sequences 0,5-10,100-120
        # we can add filtering frames list to get expected frames list
        # instead of using start and end frame
        # but if the custom frame disabled, we can still use start and end frame
        # to get expected frames list
        render_dict: Dict[str, list[str]] = {}

        # Always add beauty pass
        render_dict["beauty"] = self.get_expected_beauty(start_frame, end_frame, extension)

        # Optionally add AOVs
        renderer = get_current_renderer()
        renderer_name = str(renderer).split(":")[0]
        render_elements = self.get_render_element_and_filepath(extension)
        if render_elements and not self.is_arnold_exr(renderer, extension):
            for aov_name, aov_filepath in render_elements:
                aov_expected_files = self.get_expected_files(
                    aov_filepath,
                    start_frame,
                    end_frame,
                    aov_name,
                    renderer_name
                )
                render_dict[aov_name] = aov_expected_files

        return render_dict

    def get_multiple_render_products(
            self, outputs: list[str], cameras: list[str]
    ) -> Dict[str, list[str]]:
        """Get render output file paths for multiple cameras.

        Combines beauty and AOV extraction into a single method to eliminate
        duplicate setup code. Always includes beauty passes; optionally includes
        render elements/AOVs.

        Args:
            outputs (list[str]): A list of output file paths.
            cameras (list[str]): A list of camera names.

        Returns:
            Dict[str, list[str]]: A dictionary containing render output file
                paths for each camera (e.g., "camera01_beauty", "camera01_Cryptomatte").
        """
        renderer = get_current_renderer()
        renderer_name = str(renderer).split(":")[0]
        render_output_frames: Dict[str, list[str]] = {}
        
        for output, camera in zip(outputs, cameras):
            camera = camera.replace(":", "_")
            filename, ext = os.path.splitext(output)
            filename = filename.replace(".", "")
            ext = ext.replace(".", "")
            start_frame = int(rt.rendStart)
            end_frame = int(rt.rendEnd) + 1
            
            # Always add beauty pass
            beauty_files = self.get_expected_beauty(start_frame, end_frame, ext)
            render_output_frames[f"{camera}_beauty"] = beauty_files

            # Add AOVs
            render_elements = self.get_render_element_and_filepath(ext)
            if render_elements and not self.is_arnold_exr(renderer, ext):
                for aov_name, aov_filepath in render_elements:
                    aov_expected_files = self.get_expected_files(
                        aov_filepath,
                        start_frame,
                        end_frame,
                        aov_name,
                        renderer_name
                    )
                    render_output_frames[f"{camera}_{aov_name}"] = aov_expected_files
        
        return render_output_frames

    def get_multiple_beauty(
            self, outputs: list[str], cameras: list[str]
    ) -> Dict[str, list[str]]:
        """Get multiple beauty render output file paths.

        Args:
            outputs (list[str]): A list of output file paths.
            cameras (list[str]): A list of camera names.

        Returns:
            Dict[str, list[str]]: A dictionary containing the beauty
                render output file paths for each camera.
        """
        return self.get_multiple_render_products(outputs, cameras, include_aovs=False)

    def get_aovs(self) -> Dict[str, list[str]]:
        """Get AOV render output file paths.

        Returns:
            Dict[str, list[str]]: A dictionary containing the AOV
                render output file paths.
        """
        return self.get_render_products(include_aovs=True)

    def get_expected_beauty(
            self, start_frame: int, end_frame: int, extension: str
    ) -> list[str]:
        """Get expected beauty render output file paths for each frame.

        Args:
            start_frame (int): The starting frame number.
            end_frame (int): The ending frame number.
            extension (str): The file extension for the output files.

        Returns:
            list[str]: A list of expected beauty render output file paths.
        """
        renderer = get_current_renderer()
        renderer_name = str(renderer).split(":")[0]
        if renderer_name.startswith("V_Ray_"):
            output_path = self.get_vray_render_output(renderer, extension)
        elif renderer_name == "Arnold":
            output_path = self.get_arnold_render_output(renderer, extension)
        else:
            output_path = rt.rendOutputFilename

        return self.get_expected_files(
            output_path,
            start_frame,
            end_frame,
            "",
            renderer_name
        )


    def get_render_element_outputfilename(
        self,
        renderer: Any,
        render_elem: Any,
        index: int,
        image_format: str,
        is_multipass: bool
    ) -> str:
        """Get the output filename for a render element.

        Args:
            renderer (Any, rt.Renderers.Current): The renderer instance.
            render_elem (Any, rt.RenderTarget): The render element instance.
            index (int): The index of the render element.
            image_format (str): The image format.
            is_multipass (bool): Whether it is a multipass render element.

        Returns:
            str: The output filename for the render element.
        """
        renderer_name = str(renderer).split(":")[0]
        if renderer_name.startswith("V_Ray_"):
            return self.get_vray_render_output(
                renderer,
                image_format,
                is_render_element=is_multipass
            )

        elif renderer_name.startswith("Arnold"):
            return self.get_arnold_render_output(renderer, image_format)

        elif is_supported_renderer(renderer_name):
            return render_elem.GetRenderElementFilename(index)

        else:
            raise RuntimeError(
                f"Renderer {renderer_name} is not supported for getting"
                " render element output filename."
            )

    def get_vray_render_output(
        self,
        vr_renderer: Any,
        image_format: str,
        is_render_element: bool = False
    ) -> str:
        """Get the V-Ray render output filename.

        Args:
            vr_renderer (Any, rt.Renderers.Current): The V-Ray renderer instance.
            image_format (str): The image format.
            is_render_element (bool, optional): Whether it is a render element. Defaults to False.

        Returns:
            str: The V-Ray render output filename.
        """
        vray_settings = (
            vr_renderer.V_Ray_settings
            if "GPU" in str(vr_renderer)
            else vr_renderer
        )
        output_attr = (
            "output_rawfilename"
            if not is_render_element and image_format == "exr"
            else "output_splitfilename"
        )
        render_output = getattr(vray_settings, output_attr)
        return render_output if render_output else rt.rendOutputFilename

    def get_arnold_render_output(self, arnold_renderer: Any, extension: str) -> str:
        """Get the Arnold render output filename.

        Args:
            arnold_renderer (Any, rt.Renderers.Current): The Arnold renderer instance.
            extension (str): The file extension for the output.

        Raises:
            RuntimeError: If the Arnold renderer does not have an
                AOVManager attribute.
            RuntimeError: If the Arnold AOVManager does not have
                a drivers attribute.
            RuntimeError: If the Arnold AOVManager does not have any drivers.
            RuntimeError: If the Arnold AOVManager does not have an
                outputPath attribute.

        Returns:
            str: The Arnold render output filename.
        """
        aov_manager = arnold_renderer.AOVManager
        drivers = aov_manager.drivers
        if not drivers:
            raise RuntimeError("Arnold AOVManager does not have any drivers.")

        output_dir = aov_manager.outputPath
        # Getting the first driver
        driver = drivers[0]
        return f"{output_dir}/{driver.filenameSuffix}.{extension}"

    def get_expected_files(
        self,
        filepath: str,
        start_frame: int,
        end_frame: int,
        aov_name: str,
        renderer_name: str,
    ) -> list[str]:
        """Get expected files

        Args:
            filepath (str): filepath of the render output.
            start_frame (int): start frame of the render sequence.
            end_frame (int): end frame of the render sequence.
            aov_name (str): name of the AOV.
            renderer_name (str): name of the renderer.

        Returns:
            list[str]: List of expected file paths.
        """
        expected_aovs: list[str] = []
        directory = os.path.dirname(filepath)
        filename = os.path.basename(filepath)
        name, ext = os.path.splitext(filename)
        name = name.lstrip(".")
        aov_name = aov_name.strip()
        # use_aov_name = bool(aov_name) and (
        #     renderer_name.startswith("V_Ray_")
        #     or (
        #         renderer_name.startswith("Redshift_Renderer")
        #         and is_redshift_default_output_regex_matched(filename)
        #     )
        # )
        for frame in range(start_frame, end_frame + 1):
            aov_filename =  f"{name}.{frame:04d}{ext}"
            expected_aov = os.path.join(directory, aov_filename)
            if aov_name and renderer_name.startswith("V_Ray_"):
                aov_filename = f"{name}.{aov_name}.{frame:04d}{ext}"
            aov_filename = reformat_filename(aov_filename)
            expected_aov = os.path.join(directory, aov_filename)
            expected_aovs.append(expected_aov)

        return expected_aovs

    def get_render_element_and_filepath(
            self, image_format: str
    ) -> list[tuple[str, str]]:
        """Get render element names and their corresponding file paths.

        Args:
            image_format (str): Image format of the render output.

        Returns:
            list[tuple[str, str]]: List of tuples containing render element
                names and their corresponding file paths.
        """
        renderer = get_current_renderer()
        renderer_name = str(renderer).split(":")[0]
        expected_elements: list[tuple[str, str]] = []
        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        is_multipass = get_multipass_setting(renderer_name)
        if render_elem_num < 1:
            return expected_elements
        # get render elements from the renders
        for index in range(render_elem_num):
            renderlayer = render_elem.GetRenderElement(index)
            if self.get_render_element_by_multipass(
                renderer_name, renderlayer, is_multipass
            ):
                renderpass = str(renderlayer.elementname)
                renderlayer_filepath = self.get_render_element_outputfilename(
                    renderer,
                    render_elem,
                    index,
                    image_format,
                    is_multipass
                )
                expected_elements.append((renderpass, str(renderlayer_filepath)))

        if renderer_name.startswith("V_Ray_"):
            additional_render_elements = self._get_vray_additional_outputs(renderer, is_multipass)
            for render_element in additional_render_elements:
                filepath = self.get_vray_render_output(
                    renderer, image_format, is_render_element=True
                )
                expected_elements.append((render_element, str(filepath)))

        return expected_elements

    def get_render_element_by_multipass(
            self, renderer_name: str, renderlayer: Any, multipass: bool) -> bool:
        """Get render element name based on multipass setting.

        Args:
            renderer_name (str): The name of the renderer.
            renderlayer (Any, rt.RenderTarget): The render layer instance.
            multipass (bool): Whether multipass is enabled.

        Returns:
            bool: True if the render element should be included
                based on the multipass setting, False otherwise.
        """
        if renderer_name == "Default_Scanline_Renderer":
            return renderlayer.enabled

        if multipass or (
            not multipass and "Cryptomatte" in renderlayer.elementname
        ):
            return renderlayer.enabled

        return False

    def _get_vray_additional_outputs(self, renderer: Any, is_multipass: bool) -> list[str]:
        """Get additional V-Ray outputs like Alpha and RGB_color.

        Args:
            renderer (Any, rt.Renderers.Current): V-Ray renderer instance
            is_multipass (bool): Whether multipass is enabled

        Returns:
            list: Updated list with additional outputs
        """
        render_name = []
        if not is_multipass:
            return render_name
        if hasattr(renderer, 'output_splitAlpha') and renderer.output_splitAlpha:
            render_name.append("Alpha")
        if hasattr(renderer, 'output_splitRGB') and renderer.output_splitRGB:
            render_name.append("RGB_color")

        return render_name

    def is_arnold_exr(self, renderer: Any, image_format: str) -> bool:
        """Check if the current renderer is Arnold and the image format is EXR.

        Args:
            renderer (Any, rt.Renderers.Current): The Arnold renderer instance.
            image_format (str): The image format of the render output.

        Returns:
            bool: True if the current renderer is Arnold and the image format
                is EXR, False otherwise.
        """
        renderer_name = str(renderer).split(":")[0]
        return renderer_name.startswith("Arnold") and image_format == "exr"

    def image_format(self) -> str:
        """Get the image format of the render output.

        Returns:
            str: The image format of the render output.
        """
        return self._project_settings["max"]["RenderSettings"]["image_format"]  # noqa
