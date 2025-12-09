import os

from ayon_core.pipeline import load, get_current_host_name
from ayon_core.pipeline.load import LoadError
from ayon_core.lib.attribute_definitions import EnumDef
from ayon_core.pipeline.colorspace import (
    get_current_context_imageio_config_preset,
    get_imageio_file_rules,
    get_imageio_file_rules_colorspace_from_filepath,
)
from ayon_core.settings import get_project_settings
from ayon_max.api.pipeline import (
    containerise_texture,
)
from ayon_max.api.lib import (
    maintained_selection,
    unique_namespace,
    imprint,
    get_plugins,
)
from pymxs import runtime as rt


class ImageLoader(load.LoaderPlugin):
    """Loading image files to Slate Material Editor."""

    product_types = {"*"}
    label = "Load Image"
    extensions = {"exr", "tif", "png", "jpg", "jpeg"}
    icon = "image"
    color = "orange"
    order = 2

    bitmap_default = "osl"
    bitmap_enum_dict = {
        "vray_bitmap": "Vray Bitmap",
        "osl": "OSL Bitmap Lookup"
        }

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef("bitmap_type",
                    items=cls.bitmap_enum_dict,
                    default=cls.bitmap_default,
                    label="Bitmap Type")
        ]

    def load(self, context, name=None, namespace=None, options=None):
        file_path = os.path.normpath(self.filepath_from_context(context))
        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )
        bitmap_type = options.get("bitmap_type", self.bitmap_default)
        if bitmap_type == "vray_bitmap":
            plugin_info = get_plugins()
            if not any(plugin.startswith("vray") for plugin in plugin_info):
                raise LoadError("Vray not loaded/installed in Max..")
            texture_node = rt.VRayBitmap()
            texture_node.fileName = file_path
        else:
            texture_node = rt.OSLMap()
            texture_node.OSLPath = os.path.join(
                rt.getdir(rt.Name("maxroot")), "OSL/OSLBitmap2.osl"
            )
            texture_node.Filename = file_path

        # Get Slate Material Editor current view
        # Create Node to store the bitmap
        current_sme_view = rt.sme.GetView(rt.sme.ActiveView)
        current_sme_view.createNode(texture_node, rt.Point2(0, 0))

        return containerise_texture(
            name, context,
            texture_node, namespace,
            loader=self.__class__.__name__
        )


    def update(self, container, context):
        file_path = os.path.normpath(self.filepath_from_context(context))
        repre_entity = context["representation"]
        texture_node = container["texture_node"]
        if rt.classOf(texture_node) == rt.VRayBitmap:
            texture_node.fileName = file_path
        elif rt.classOf(texture_node) == rt.OSLMap:
            texture_node.Filename = file_path

        imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        from pymxs import runtime as rt
        container_node = rt.GetNodeByName(container["instance_node"])
        # TODO: remove the texture node from SME
        # some contextlib selection management may be needed
        rt.Delete(container_node)
