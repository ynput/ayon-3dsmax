import pyblish.api
import os
import sys
import platform
import tempfile


from pymxs import runtime as rt
from ayon_core.lib import run_subprocess
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
        filename, ext = os.path.splitext(current_filename)
        fmt = RenderProducts().image_format()
        cameras = instance.data.get("cameras")
        if not cameras:
            return
        new_folder = f"{current_folder}_{filename}"
        os.makedirs(new_folder, exist_ok=True)
        render_settings = RenderSettings(data=instance.data)
        maxbatch_exe = os.path.join(
            os.path.dirname(sys.executable), "3dsmaxbatch")
        maxbatch_exe = maxbatch_exe.replace("\\", "/")
        if platform.system().lower() == "windows":
            maxbatch_exe += ".exe"
            maxbatch_exe = os.path.normpath(maxbatch_exe)
        scene_filepath = current_filepath.replace("\\", "/")
        for camera in cameras:
            new_output = render_settings.get_batch_render_output(camera)       # noqa
            new_output = new_output.replace("\\", "/")
            camera_name = camera.replace(":", "_")
            new_filename = f"{filename}_{camera_name}{ext}"
            new_filepath = os.path.join(new_folder, new_filename)
            new_filepath = new_filepath.replace("\\", "/")
            render_settings.batch_render_elements(camera)
            rt.rendOutputFilename = new_output
            script = ("""
from pymxs import runtime as rt
import os
filename = "{filename}"
new_filepath = "{new_filepath}"
new_output = "{new_output}"
camera = "{camera}"
farm = {farm}
camera_name = camera.replace(":", "_")
target_camera_node = rt.getNodeByName(camera)
rt.viewport.setCamera(target_camera_node)
rt.rendOutputFilename = new_output
directory = os.path.dirname(rt.rendOutputFilename)
directory = os.path.join(directory, filename)
if not os.path.exists(directory):
    os.mkdir(directory)
render_elem = rt.maxOps.GetCurRenderElementMgr()
render_elem_num = render_elem.NumRenderElements()
if render_elem_num > 0:
    ext = "{ext}"
    for i in range(render_elem_num):
        renderlayer_name = render_elem.GetRenderElement(i)
        target, renderpass = str(renderlayer_name).split(":")
        aov_name =  f"{{directory}}_{{camera_name}}_{{renderpass}}..{ext}"
        render_elem.SetRenderElementFileName(i, aov_name)
rt.saveMaxFile(new_filepath)
if not farm:
    for frame in range(int(rt.rendStart), int(rt.rendEnd) + 1):
        rt.render(outputFile=rt.rendOutputFilename, frame=frame, vfb=False)
        """).format(filename=instance.name,
                    new_filepath=new_filepath,
                    new_output=new_output,
                    camera=camera,
                    ext=fmt,
                    farm=instance.data.get("farm"))
            # Write and run only the current camera's script. Accumulating
            # them made every camera re-run the previous cameras as well.
            with tempfile.TemporaryDirectory() as tmp_dir_name:
                tmp_script_path = os.path.join(
                    tmp_dir_name, "extract_scene_files.py")
                self.log.info(
                    "Using script file: {}".format(tmp_script_path))
                with open(tmp_script_path, "wt") as tmp:
                    tmp.write(script + "\n")

                tmp_script_path = tmp_script_path.replace("\\", "/")
                run_subprocess([maxbatch_exe, tmp_script_path,
                                "-sceneFile", scene_filepath],
                                logger=self.log)

            if not os.path.exists(new_filepath):
                self.log.error("Camera scene files not existed yet!")
                raise RuntimeError("MaxBatch.exe doesn't run as expected")
            self.log.debug(f"Found Camera scene:{new_filepath}")
