import pyblish.api
import os
import platform
import tempfile


from pymxs import runtime as rt

from ayon_core.lib import run_subprocess
from ayon_core.pipeline.publish import PublishError
from ayon_max.api.lib_rendersettings import RenderSettings
from ayon_max.api.lib_renderproducts import RenderProducts


class SaveScenesForCamera(pyblish.api.InstancePlugin):
    """Save scene files for multiple cameras without
    editing the original scene before deadline submission

    """

    label = "Save Scene files for cameras"
    order = pyblish.api.ExtractorOrder - 0.48
    hosts = ["max"]
    families = ["maxrender"]

    def process(self, instance):
        if not instance.data.get("multiCamera"):
            self.log.debug(
                "Multi Camera disabled. "
                "Skipping to save scene files for cameras")
            return
        current_folder = rt.maxFilePath
        current_filename = rt.maxFileName
        current_filepath = os.path.join(current_folder, current_filename)
        camera_scene_files = []
        scripts = []
        filename, ext = os.path.splitext(current_filename)
        render_products = RenderProducts()
        fmt = render_products.image_format()
        cameras = instance.data.get("cameras")
        if not cameras:
            return
        new_folder = f"{current_folder}_{filename}"
        os.makedirs(new_folder, exist_ok=True)
        render_settings = RenderSettings(data=instance.data)

        # `CollectFramesFixDefMax` decides which frames have to be rendered when
        # frames to fix are used; the remaining frames are copied from the
        # previous published version by `ExtractLastPublished`. The frames are
        # embedded into the batch script below because it is executed in a
        # separate 3dsmaxbatch process.
        frames_to_render = instance.data.get("frames_to_render")
        if frames_to_render:
            self.log.info(
                "Multi camera render, rendering only: %s", frames_to_render
            )
            frames_expression = str(list(frames_to_render))
        else:
            frames_expression = (
                "range(int(rt.rendStart), int(rt.rendEnd) + 1)")

        # V-Ray and Arnold write the render elements through their own output
        # settings (raw/split file or AOV manager), only the other renderers use
        # the render element filenames of the scene.
        renderer_name = str(rt.renderers.production).split(":")[0]
        if renderer_name.startswith(("V_Ray_", "Arnold")):
            element_block = ""
        else:
            element_block = (
                'render_elem = rt.maxOps.GetCurRenderElementMgr()\n'
                'render_elem_num = render_elem.NumRenderElements()\n'
                'if render_elem_num > 0:\n'
                '    ext = "{ext}"\n'
                '    aov_base = os.path.splitext(new_output)[0].rstrip(".")\n'
                '    for i in range(render_elem_num):\n'
                '        renderlayer_name = render_elem.GetRenderElement(i)\n'
                '        target, renderpass = '
                'str(renderlayer_name).split(":")\n'
                '        aov_name = f"{{aov_base}}_{{renderpass}}..{ext}"\n'
                '        render_elem.SetRenderElementFileName(i, aov_name)\n'
            ).format(ext=fmt)

        for camera in cameras:
            new_output = render_settings.get_batch_render_output(camera)       # noqa
            new_output = new_output.replace("\\", "/")
            camera_name = camera.replace(":", "_")
            new_filename = f"{filename}_{camera_name}{ext}"
            new_filepath = os.path.join(new_folder, new_filename)
            new_filepath = new_filepath.replace("\\", "/")
            camera_scene_files.append(new_filepath)
            render_settings.batch_render_elements(camera)
            rt.rendOutputFilename = new_output
            rt.saveMaxFile(current_filepath)
            # The renderer specific outputs of the camera. V-Ray needs the raw
            # or split filename per camera, otherwise every camera writes into
            # the same file; the expected files are derived from the same paths
            # by `RenderProducts.get_multiple_camera_outputs`.
            camera_outputs = render_products.get_multiple_camera_outputs(
                new_output, camera_name, fmt)
            # The render output of a new version does not exist before the
            # integration, create it (also on the farm submission path) so the
            # render task does not fail with a missing directory.
            os.makedirs(os.path.dirname(new_output), exist_ok=True)
            script = ("""
from pymxs import runtime as rt
import os
new_filepath = "{new_filepath}"
new_output = "{new_output}"
camera = "{camera}"
farm = {farm}
target_camera_node = rt.getNodeByName(camera)
rt.viewport.setCamera(target_camera_node)
rt.rendOutputFilename = new_output
os.makedirs(os.path.dirname(new_output), exist_ok=True)
renderer_name = str(rt.renderers.production).split(":")[0]
raw_output = "{raw_output}"
split_output = "{split_output}"
arnold_output = "{arnold_output}"
if renderer_name.startswith("V_Ray_"):
    vr_settings = rt.renderers.production
    if "GPU" in renderer_name:
        vr_settings = rt.renderers.production.V_Ray_settings
    if raw_output:
        vr_settings.output_saverawfile = True
        vr_settings.output_rawfilename = raw_output
    if split_output:
        vr_settings.output_splitgbuffer = True
        vr_settings.output_splitfilename = split_output
elif renderer_name.startswith("Arnold"):
    if arnold_output:
        rt.renderers.production.AOVManager.outputPath = arnold_output
{element_block}rt.saveMaxFile(new_filepath)
if not farm:
    for frame in {render_frames}:
        rt.render(outputFile=rt.rendOutputFilename, camera=target_camera_node,frame=frame, vfb=False)
        """).format(new_filepath=new_filepath,
                    new_output=new_output,
                    camera=camera,
                    raw_output=camera_outputs["raw"],
                    split_output=camera_outputs["split"],
                    arnold_output=camera_outputs["arnold"],
                    element_block=element_block,
                    farm=instance.data.get("farm"),
                    render_frames=frames_expression)
            scripts.append(script)
        maxbatch_exe = self.get_maxbatch_executable()
        with tempfile.TemporaryDirectory() as tmp_dir_name:
            tmp_script_path = os.path.join(
                tmp_dir_name, "extract_scene_files.py")
            self.log.info("Using script file: {}".format(tmp_script_path))
            with open(tmp_script_path, "wt", encoding="utf-8") as tmp:
                for script in scripts:
                    tmp.write(script + "\n")

            full_script = "\n".join(scripts)
            current_filepath = current_filepath.replace("\\", "/")
            tmp_script_path = tmp_script_path.replace("\\", "/")
            run_subprocess([maxbatch_exe, tmp_script_path,
                            "-sceneFile", current_filepath])

        for camera_scene in camera_scene_files:
            if not os.path.exists(camera_scene):
                full_script = "\n".join(scripts)
                self.log.debug(f"Failed running script {tmp_script_path}:\n{full_script}")
                self.log.error("Camera scene files not existed yet!")
                raise RuntimeError("MaxBatch.exe doesn't run as expected")
            self.log.debug(f"Found Camera scene:{camera_scene}")

    @staticmethod
    def get_maxbatch_executable():
        """Get the path of the 3dsmaxbatch executable.

        3dsmaxbatch is not necessarily next to `sys.executable`: the Python
        embedded in 3ds Max lives in a subfolder of the installation, which does
        not contain the executable.

        Returns:
            str: Full path to the 3dsmaxbatch executable.

        Raises:
            PublishError: When the executable cannot be found.

        """
        executable = "3dsmaxbatch"
        if platform.system().lower() == "windows":
            executable += ".exe"
        max_root = rt.getdir(rt.Name("maxroot"))
        executable = os.path.join(max_root, executable)
        if os.path.exists(executable):
            return os.path.normpath(executable)
        raise PublishError(f"Could not find the '{executable}' executable.")