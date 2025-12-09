import os

from ayon_core.pipeline import load
from ayon_core.pipeline.load import LoadError
from ayon_core.lib.attribute_definitions import EnumDef
from ayon_max.api.pipeline import (
    containerise_texture,
)
from ayon_max.api.lib import (
    unique_namespace,
    imprint,
    get_plugins,
    get_target_sme_view,
    get_texture_node_from_sme_view,
    ensure_sme_editor_active,
)
from pymxs import runtime as rt


class ImageLoader(load.LoaderPlugin):
    """Loading image files to Slate Material Editor."""

    product_types = {"render", "image", "plate", "texture"}
    representations = {"*"}
    label = "Load Image"
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
                raise LoadError("Vray not loaded/installed in Max.")
            texture_node = rt.VRayBitmap()
            texture_node.fileName = file_path
        else:
            texture_node = rt.OSLMap()
            texture_node.OSLPath = os.path.join(
                rt.getdir(rt.Name("maxroot")), "OSL/OSLBitmap2.osl"
            )
            texture_node.Filename = file_path

        # add the contextlib to check whether sml is opened.
        # Get Slate Material Editor current view
        # Create Node to store the bitmap
        with ensure_sme_editor_active():
            active_view_number = rt.sme.ActiveView
            current_sme_view = get_target_sme_view(active_view_number)
            view_node = current_sme_view.createNode(texture_node, rt.Point2(0, 0))

        return containerise_texture(
            name,
            context,
            view_node.name,
            active_view_number,
            namespace,
            loader=self.__class__.__name__
        )

    def update(self, container, context):
        file_path = os.path.normpath(self.filepath_from_context(context))
        repre_entity = context["representation"]
        view_node_name = container["view_node"]
        sme_view_number = container["sme_view_number"]
        with ensure_sme_editor_active():
            current_sme_view = get_target_sme_view(sme_view_number)
            view_node = get_texture_node_from_sme_view(
                current_sme_view, view_node_name
            )
            texture_node = current_sme_view.GetNodeByRef(view_node.reference)

            if rt.classOf(texture_node) == rt.VRayBitmap:
                texture_node.fileName = file_path
            else:
                texture_node.Filename = file_path

        imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        container_node = rt.GetNodeByName(container["instance_node"])
        # TODO: remove the texture node from SME
        # some contextlib selection management may be needed
        rt.Delete(container_node)
