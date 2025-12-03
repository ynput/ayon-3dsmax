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
                if not renderer_class.output_splitgbuffer:
                    return aovs_frames

                render_name = self.get_render_elements_name()
                render_name = self._add_vray_additional_outputs(render_name, renderer_class)
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
            # elif renderer == "Arnold":
            #     aov_by_render_name, output_file = self.get_arnold_product_name_and_path()
            #     if aov_by_render_name:
            #         aovs_frames.update({
            #             f"{camera}_{name}": self.get_expected_arnold_product(   # noqa
            #                 output_file, aov_by_render_name, start_frame,
            #                 end_frame, ext)
            #         })

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
            if not renderer_class.output_splitgbuffer:
                return render_dict

            render_name = self.get_render_elements_name()
            render_name = self._add_vray_additional_outputs(render_name, renderer_class)

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

        # TODO: implement aovs
        # elif renderer == "Arnold":
        #     aov_by_render_name, output_file = self.get_arnold_product_name_and_path()
        #     render_dict.update({
        #         name: self.get_expected_arnold_product(
        #             output_file, aov_by_render_name, start_frame,
        #             end_frame, img_fmt)
        #     })

        return render_dict

    def get_expected_beauty(self, folder, start_frame, end_frame, fmt, renderer):
        """Get expected beauty render output file paths for each frame."""
        beauty_frame_range = []

        if renderer.startswith("V_Ray_"):
            vr_renderer = get_current_renderer()
            if fmt == "exr":
                raw_directory, raw_fname = self.get_vray_render_files(vr_renderer)
                for frame_num in range(start_frame, end_frame):
                    frame = f"{frame_num:04d}"
                    output_path = f"{raw_directory}/{raw_fname}.{frame}.{fmt}"
                    beauty_frame_range.append(output_path.replace("\\", "/"))

        elif renderer == "Arnold":
            aov_by_name, output_file = self.get_arnold_product_name_and_path()
            beauty_frame_range.extend(
                self.get_expected_arnold_product(
                    output_file, aov_by_name, start_frame,
                    end_frame, fmt)
            )
        else:
            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                output_path = f"{folder}.{frame}.{fmt}"
                beauty_frame_range.append(output_path.replace("\\", "/"))

        return beauty_frame_range

    def get_arnold_product_name_and_path(self):
        """Get all the Arnold AOVs name and output path from AOV manager."""
        aov_name_by_render_name = {}
        # amw = rt.MaxToAOps.AOVsManagerWindow()
        aov_mgr = rt.renderers.current.AOVManager
        aov_output_path = rt.renderers.current.AOVManager.outputPath
        # Check if there is any aov group set in AOV manager
        aov_group_num = len(aov_mgr.drivers)
        if aov_group_num < 1:
            return
        for i in range(aov_group_num):
            # get the specific AOV group
            aov_name = aov_mgr.drivers[i].filenameSuffix
            if aov_name is None:
                aov_name = ""
            aov_name_by_render_name.update({
                aov_name: [aov.name for aov in aov_mgr.drivers[i].aov_list]
            })
        # # close the AOVs manager window
        # amw.close()

        return aov_name_by_render_name, aov_output_path

    def get_expected_arnold_product(self, folder, name,
                                    start_frame, end_frame, fmt):
        """Get all the expected Arnold AOVs"""
        aov_list = []
        for aov_group in name.keys():
            rendername = f"{folder}/{aov_group}."
            for f in range(start_frame, end_frame):
                frame = "%04d" % f
                render_element = f"{rendername}{frame}.{fmt}"
                render_element = render_element.replace("\\", "/")
                aov_list.append(render_element)

        return aov_list

    def get_render_elements_name(self):
        """Get all the render element names for general """
        render_name = []
        render_elem = rt.maxOps.GetCurRenderElementMgr()
        render_elem_num = render_elem.NumRenderElements()
        if render_elem_num < 1:
            return render_name
        # get render elements from the renders
        for i in range(render_elem_num):
            renderlayer_name = render_elem.GetRenderElement(i)
            if renderlayer_name.enabled:
                _, renderpass = str(renderlayer_name).split(":")
                render_name.append(renderpass)

        return render_name

    def _add_vray_additional_outputs(self, render_name, renderer_class):
        """Add additional V-Ray outputs like Alpha and RGB_color to render names.

        Args:
            render_name (list): List of existing render element names
            renderer_class: V-Ray renderer instance

        Returns:
            list: Updated list with additional outputs
        """
        if renderer_class.output_splitAlpha:
            render_name.append("Alpha")
        if hasattr(renderer_class, 'output_splitRGB') and renderer_class.output_splitRGB:
            render_name.append("RGB_color")

        return render_name

    def get_expected_aovs(self, folder, name, start_frame, end_frame, fmt, renderer):
        """Get all the expected render element output files."""
        render_elements = []

        if renderer.startswith("V_Ray_"):
            vr_renderer = get_current_renderer()
            raw_directory, raw_fname = self.get_vray_render_files(
                vr_renderer, is_render_element=True)
            if vr_renderer.output_separateFolders:
                formated_output = f"{raw_directory}/{name}/{raw_fname}.{name}"
            else:
                formated_output = f"{raw_directory}/{raw_fname}.{name}"

            for frame_num in range(start_frame, end_frame):
                frame = f"{frame_num:04d}"
                render_element = f"{formated_output}.{frame}.{fmt}"
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
            vr_renderer (rt.renderers.production): The V-Ray renderer instance.
            is_render_element (bool): whether type of output are
            render element files.

        Returns:
            str, str: The raw directory and filename for V-Ray renderer.
        """
        raw_filepath = vr_renderer.output_rawfilename
        if not raw_filepath or is_render_element:
            if "GPU" in str(vr_renderer):
                raw_filepath = vr_renderer.V_Ray_settings.output_rawfilename
            else:
                raw_filepath = vr_renderer.output_splitfilename

        raw_directory = os.path.dirname(raw_filepath)
        raw_filename = os.path.basename(raw_filepath)
        raw_fname, _ = os.path.splitext(raw_filename)
        return raw_directory, raw_fname.strip(".")

    def image_format(self):
        return self._project_settings["max"]["RenderSettings"]["image_format"]  # noqa
