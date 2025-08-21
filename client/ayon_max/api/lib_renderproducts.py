# Render Element Example : For scanline render, VRay
# https://help.autodesk.com/view/MAXDEV/2022/ENU/?guid=GUID-E8F75D47-B998-4800-A3A5-610E22913CFC
# arnold
# https://help.autodesk.com/view/ARNOL/ENU/?guid=arnold_for_3ds_max_ax_maxscript_commands_ax_renderview_commands_html
import os

from pymxs import runtime as rt

from ayon_max.api.lib import get_current_renderer
from ayon_core.pipeline import get_current_project_name
from ayon_core.settings import get_project_settings


class RenderProducts(object):

    def __init__(self, project_settings=None):
        self._project_settings = project_settings
        if not self._project_settings:
            self._project_settings = get_project_settings(
                get_current_project_name()
            )

    def get_beauty(self, container, renderer):
        """Get beauty render output file path."""
        render_dir = os.path.dirname(rt.rendOutputFilename)

        output_file = os.path.join(render_dir, container)

        setting = self._project_settings
        img_fmt = setting["max"]["RenderSettings"]["image_format"]   # noqa

        start_frame = int(rt.rendStart)
        end_frame = int(rt.rendEnd) + 1
        return {
            "beauty": self.get_expected_beauty(
                output_file, start_frame, end_frame, img_fmt,
                renderer
            )
        }

    def get_multiple_beauty(self, outputs, cameras):
        beauty_output_frames = dict()
        renderer = get_current_renderer()
        for output, camera in zip(outputs, cameras):
            camera = camera.replace(":", "_")
            filename, ext = os.path.splitext(output)
            filename = filename.replace(".", "")
            ext = ext.replace(".", "")
            start_frame = int(rt.rendStart)
            end_frame = int(rt.rendEnd) + 1
            new_beauty = self.get_expected_beauty(
                filename, start_frame, end_frame, ext,
                renderer
            )
            beauty_output = ({
                f"{camera}_beauty": new_beauty
            })
            beauty_output_frames.update(beauty_output)
        return beauty_output_frames

    def get_multiple_aovs(self, outputs, cameras):
        renderer_class = get_current_renderer()
        renderer = str(renderer_class).split(":")[0]
        aovs_frames = {}
        for output, camera in zip(outputs, cameras):
            camera = camera.replace(":", "_")
            filename, ext = os.path.splitext(output)
            filename = filename.replace(".", "")
            ext = ext.replace(".", "")
            start_frame = int(rt.rendStart)
            end_frame = int(rt.rendEnd) + 1

            if renderer in [
                "ART_Renderer",
                "Default_Scanline_Renderer",
                "Quicksilver_Hardware_Renderer",
            ]:
                render_name = self.get_render_elements_name()
                if render_name:
                    for name in render_name:
                        aovs_frames.update({
                            f"{camera}_{name}": self.get_expected_aovs(
                                filename, name, start_frame,
                                end_frame, ext, renderer)
                        })
            elif renderer.startswith("V_Ray_"):
                if renderer_class.output_splitgbuffer:
                    render_name = self.get_render_elements_name()
                    if renderer_class.output_splitAlpha:
                        render_name.append("Alpha")
                    if render_name:
                        for name in render_name:
                            aovs_frames.update({
                                f"{camera}_{name}": self.get_expected_aovs(
                                filename, name, start_frame,
                                end_frame, ext, renderer)
                        })
            elif renderer == "Redshift_Renderer":
                render_name = self.get_render_elements_name()
                if render_name:
                    rs_aov_files = rt.Execute("renderers.current.separateAovFiles")     # noqa
                    # this doesn't work, always returns False
                    # rs_AovFiles = rt.RedShift_Renderer().separateAovFiles
                    if ext == "exr" and not rs_aov_files:
                        for name in render_name:
                            if name == "RsCryptomatte":
                                aovs_frames.update({
                                    f"{camera}_{name}": self.get_expected_aovs(
                                        filename, name, start_frame,
                                        end_frame, ext, renderer)
                                })
                    else:
                        for name in render_name:
                            aovs_frames.update({
                                f"{camera}_{name}": self.get_expected_aovs(
                                    filename, name, start_frame,
                                    end_frame, ext, renderer)
                            })
            elif renderer == "Arnold":
                render_name = self.get_arnold_product_name()
                if render_name:
                    for name in render_name:
                        aovs_frames.update({
                            f"{camera}_{name}": self.get_expected_arnold_product(   # noqa
                                filename, name, start_frame,
                                end_frame, ext, renderer)
                        })

        return aovs_frames

    def get_aovs(self, container):
        render_dir = os.path.dirname(rt.rendOutputFilename)

        output_file = os.path.join(render_dir,
                                   container)

        setting = self._project_settings
        img_fmt = setting["max"]["RenderSettings"]["image_format"]   # noqa

        start_frame = int(rt.rendStart)
        end_frame = int(rt.rendEnd) + 1
        renderer_class = get_current_renderer()
        renderer = str(renderer_class).split(":")[0]
        render_dict = {}

        if renderer in [
            "ART_Renderer",
            "Default_Scanline_Renderer",
            "Quicksilver_Hardware_Renderer",
        ]:
            render_name = self.get_render_elements_name()
            if render_name:
                for name in render_name:
                    render_dict.update({
                        name: self.get_expected_aovs(
                            output_file, name, start_frame,
                            end_frame, img_fmt,
                            renderer)
                    })
        elif renderer.startswith("V_Ray_"):
            if renderer_class.output_splitgbuffer:
                render_name = self.get_render_elements_name()
                if renderer_class.output_splitAlpha:
                    render_name.append("Alpha")
                # Add RGB_color suffix if splitgbuffer is enabled
                if renderer_class.output_splitRGB:
                    render_name.append("RGB_color")

                if render_name:
                    for name in render_name:
                        render_dict.update({
                            name: self.get_expected_aovs(
                                output_file, name, start_frame,
                                end_frame, img_fmt,
                                renderer)
                        })
        elif renderer == "Redshift_Renderer":
            render_name = self.get_render_elements_name()
            if render_name:
                rs_aov_files = rt.Execute("renderers.current.separateAovFiles")
                # this doesn't work, always returns False
                # rs_AovFiles = rt.RedShift_Renderer().separateAovFiles
                if img_fmt == "exr" and not rs_aov_files:
                    for name in render_name:
                        if name == "RsCryptomatte":
                            render_dict.update({
                                name: self.get_expected_aovs(
                                    output_file, name, start_frame,
                                    end_frame, img_fmt,
                                    renderer)
                            })
                else:
                    for name in render_name:
                        render_dict.update({
                            name: self.get_expected_aovs(
                                output_file, name, start_frame,
                                end_frame, img_fmt,
                                renderer)
                        })

        elif renderer == "Arnold":
            render_name = self.get_arnold_product_name()
            if render_name:
                for name in render_name:
                    render_dict.update({
                        name: self.get_expected_arnold_product(
                            output_file, name, start_frame,
                            end_frame, img_fmt)
                    })

        return render_dict

    def get_expected_beauty(self, folder, start_frame, end_frame, fmt, renderer):
        """Get expected beauty render output file paths for each frame."""
        beauty_frame_range = []

        if renderer.startswith("V_Ray_") and fmt == "exr":
            vr_renderer = get_current_renderer()
            raw_directory, raw_fname = self.get_vray_render_files(vr_renderer)
            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                output_path = f"{raw_directory}/{raw_fname}.{frame}{fmt}"
                beauty_frame_range.append(output_path.replace("\\", "/"))
        else:
            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                output_path = f"{folder}.{frame}.{fmt}"
                beauty_frame_range.append(output_path.replace("\\", "/"))

        return beauty_frame_range

    def get_arnold_product_name(self):
        """Get all the Arnold AOVs name"""
        aov_name = []

        amw = rt.MaxToAOps.AOVsManagerWindow()
        aov_mgr = rt.renderers.current.AOVManager
        # Check if there is any aov group set in AOV manager
        aov_group_num = len(aov_mgr.drivers)
        if aov_group_num < 1:
            return
        for i in range(aov_group_num):
            # get the specific AOV group
            aov_name.extend(aov.name for aov in aov_mgr.drivers[i].aov_list)
        # close the AOVs manager window
        amw.close()

        return aov_name

    def get_expected_arnold_product(self, folder, name,
                                    start_frame, end_frame, fmt):
        """Get all the expected Arnold AOVs"""
        aov_list = []
        for f in range(start_frame, end_frame):
            frame = "%04d" % f
            render_element = f"{folder}_{name}.{frame}.{fmt}"
            render_element = render_element.replace("\\", "/")
            aov_list.append(render_element)

        return aov_list

    def get_render_elements_name(self):
        """Get all the render element names for general """
        render_name = []
        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        if render_elem_num < 1:
            return
        # get render elements from the renders
        for i in range(render_elem_num):
            renderlayer_name = render_elem.GetRenderElement(i)
            if renderlayer_name.enabled:
                target, renderpass = str(renderlayer_name).split(":")
                render_name.append(renderpass)

        return render_name

    def get_expected_aovs(self, folder, name, start_frame, end_frame, fmt, renderer):
        """Get all the expected render element output files."""
        render_elements = []

        if renderer.startswith("V_Ray_"):
            vr_renderer = get_current_renderer()
            raw_directory, raw_fname = self.get_vray_render_files(
                vr_renderer, is_render_element=True)

            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                render_element = (
                    f"{raw_directory}/{raw_fname}.{name}.{frame}.{fmt}"
                )
                render_elements.append(render_element.replace("\\", "/"))
        else:
            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                render_element = f"{folder}_{name}.{frame}.{fmt}"
                render_elements.append(render_element.replace("\\", "/"))

        return render_elements

    def get_vray_render_files(self, vr_renderer, is_render_element=False):
        """Get the raw directory and filename for V-Ray renderer.

        Args:
            vr_renderer (str): The V-Ray renderer instance.
            is_render_element (bool): whether type of output are
            render element files.

        Returns:
            str, str: The raw directory and filename for V-Ray renderer.
        """
        raw_filepath = vr_renderer.V_Ray_settings.output_rawfilename
        if not raw_filepath or is_render_element:
            raw_filepath = vr_renderer.V_Ray_settings.output_splitfilename

        raw_directory = os.path.dirname(raw_filepath)
        raw_filename = os.path.basename(raw_filepath)
        raw_fname, _ = os.path.splitext(raw_filename)
        return raw_directory, raw_fname

    def image_format(self):
        return self._project_settings["max"]["RenderSettings"]["image_format"]  # noqa
