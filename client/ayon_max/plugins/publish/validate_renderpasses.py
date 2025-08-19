import os
import pyblish.api
from pymxs import runtime as rt
from ayon_core.pipeline.publish import (
    RepairAction,
    ValidateContentsOrder,
    PublishValidationError,
    OptionalPyblishPluginMixin
)
from ayon_max.api.lib_rendersettings import (
    RenderSettings,
    is_supported_renderer
)


class ValidateRenderPasses(OptionalPyblishPluginMixin,
                           pyblish.api.InstancePlugin):
    """Validates Render Passes before farm submission
    """

    order = ValidateContentsOrder
    families = ["maxrender"]
    hosts = ["max"]
    label = "Validate Render Passes"
    actions = [RepairAction]

    settings_category = "max"

    def process(self, instance):
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
    def get_invalid(cls, instance):
        """Function to get invalid beauty render outputs and
        render elements.

        1. Check Render Output Folder matches the name of
           the current Max Scene, e.g.
             The name of the current Max scene:
               John_Doe.max
             The expected render output directory:
               {root[work]}/{project[name]}/{hierarchy}/{asset}/
               work/{task[name]}/render/3dsmax/John_Doe/

        2. Check image extension(s) of the render output(s)
           matches the image format in OP/AYON setting, e.g.
               The current image format in settings: png
               The expected render outputs: John_Doe.png

        3. Check filename of render element ends with the name of
           render element from the 3dsMax Render Element Manager.
           e.g. The name of render element: RsCryptomatte
            The expected filename: {InstanceName}_RsCryptomatte.png

        Args:
            instance (pyblish.api.Instance): instance
            workfile_name (str): filename of the Max scene

        Returns:
            list: list of invalid filename which doesn't match
                with the project name
        """
        invalid = []
        file = rt.maxFileName
        workfile_name, ext = os.path.splitext(file)
        if workfile_name not in rt.rendOutputFilename:
            cls.log.error(
                "Render output folder must include"
                f" the max scene name {workfile_name} "
            )
            invalid_folder_name = os.path.dirname(
                rt.rendOutputFilename).replace(
                    "\\", "/").split("/")[-1]
            invalid.append(("Invalid Render Output Folder",
                            invalid_folder_name))
        beauty_fname = os.path.basename(rt.rendOutputFilename)
        beauty_name, ext = os.path.splitext(beauty_fname)
        invalid_filenames = cls.get_invalid_filenames(
            instance, beauty_name, ext)
        invalid.extend(invalid_filenames)
        invalid_image_format = cls.get_invalid_image_format(
            instance, ext.lstrip("."))
        invalid.extend(invalid_image_format)
        renderer = instance.data["renderer"]
        if is_supported_renderer(renderer):
            render_elem = rt.maxOps.GetCurRenderElementMgr()
            render_elem_num = render_elem.NumRenderElements()
            for i in range(render_elem_num):
                renderlayer_name = render_elem.GetRenderElement(i)
                renderpass = str(renderlayer_name).rsplit(":", 1)[-1]
                rend_file = render_elem.GetRenderElementFilename(i)
                if not rend_file:
                    continue
                render_filename = os.path.basename(rend_file)
                rend_fname, ext = os.path.splitext(render_filename)
                invalid_image_format = cls.get_invalid_image_format(
                    instance, ext)
                invalid_filenames = cls.get_invalid_filenames(
                    instance, rend_fname, ext, renderpass=renderpass,
                    render_filename=render_filename)
                invalid.extend(invalid_filenames)
                invalid.extend(invalid_image_format)
        elif renderer == "Arnold":
            cls.log.debug(
                "Renderpass validation does not support Arnold yet,"
                " validation skipped...")
        else:
            cls.log.debug(
                "Skipping render element validation "
                f"for renderer: {renderer}")
        return invalid

    @classmethod
    def get_invalid_filenames(
        cls, instance, file_name,
        ext, renderpass=None,
        render_filename=None):
        """Function to get invalid filenames from render outputs.

        Args:
            instance (pyblish.api.Instance): instance
            file_name (str): name of the file
            ext (str): image extension
            renderpass (str, optional): name of the renderpass.
                Defaults to None.
            render_filename(str, optional): render filename

        Returns:
            list: invalid filenames
        """
        invalid = []
        if instance.name not in file_name:
            cls.log.error("The renderpass filename should contain the instance name.")
            invalid.append(("Invalid instance name",
                            file_name))
        if renderpass is not None and render_filename is not None:
            renderpass_token = f"{renderpass}.{ext}"
            if not render_filename.endswith(renderpass_token):
                cls.log.error(f"{render_filename}: {renderpass_token}")
                cls.log.error(
                    f"Filename for {renderpass} should "
                    f"end with {renderpass}: {render_filename}"
                )
                invalid.append((f"Invalid {renderpass}",
                                render_filename))
        return invalid

    @classmethod
    def get_invalid_image_format(cls, instance, ext):
        """Function to check if the image format of the render outputs
        aligns with that in the setting.

        Args:
            instance (pyblish.api.Instance): instance
            ext (str): image extension

        Returns:
            list: list of files with invalid image format
        """
        invalid = []
        settings = instance.context.data["project_settings"].get("max")
        image_format = settings["RenderSettings"]["image_format"]
        ext = ext.lstrip(".")
        if ext != image_format:
            msg = (
                f"Invalid image format {ext} for render outputs.\n"
                f"Should be: {image_format}")
            cls.log.error(msg)
            invalid.append((msg, ext))
        return invalid

    @classmethod
    def repair(cls, instance):
        container = instance.data.get("instance_node")
        # TODO: need to rename the function of render_output
        RenderSettings().render_output(container)
        cls.log.debug("Finished repairing the render output "
                      "folder and filenames.")
