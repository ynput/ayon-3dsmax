import os
import contextlib
from ayon_core.pipeline import load, get_current_host_name
from ayon_core.pipeline.load import LoadError

from ayon_core.lib.attribute_definitions import EnumDef
from ayon_max.api.pipeline import (
    containerise_texture,
)
from ayon_core.pipeline.colorspace import (
    get_current_context_imageio_config_preset,
    get_imageio_file_rules,
    get_imageio_file_rules_colorspace_from_filepath,
)
from ayon_core.settings import get_project_settings
from ayon_max.api.lib import (
    unique_namespace,
    imprint,
    find_plugins,
    get_target_sme_view,
    get_view_node_from_sme_view,
    ensure_sme_editor_active,
    maintained_sme_view_nodes_selection,
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
        "osl": "OSL Bitmap Lookup",
    }

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef(
                "bitmap_type",
                items=cls.bitmap_enum_dict,
                default=cls.bitmap_default,
                label="Bitmap Type"
            )
        ]

    def _create_texture_node(self, bitmap_type, file_path, context):
        """Create texture node based on bitmap type.
        
        Args:
            bitmap_type (str): Type of bitmap ("vray_bitmap" or "osl")
            file_path (str): Path to the image file
            context (dict): Load context
            
        Returns:
            Node: The created texture node
        """
        if bitmap_type == "vray_bitmap":
            if not find_plugins("vray"):
                raise LoadError("V-Ray plugin is not available in 3ds Max.")
            texture_node = rt.VRayBitmap()
            texture_node.fileName = file_path
        elif bitmap_type == "osl":
            texture_node = rt.OSLMap()
            texture_node.OSLPath = os.path.join(
                rt.getdir(rt.Name("maxroot")), "OSL/OSLBitmap2.osl"
            )
            texture_node.Filename = file_path
            self._set_udim(context, texture_node)
            texture_node.Filename_ColorSpace = self._get_colorspace(context)
        else:
            raise LoadError(f"Unsupported bitmap type: {bitmap_type}")

        return texture_node

    def load(self, context, name=None, namespace=None, options=None):
        file_path = os.path.normpath(self.filepath_from_context(context))
        folder_name = context["folder"]["name"]
        namespace = unique_namespace(
            f"{folder_name}_{name}" + "_",
            suffix="_",
        )
        bitmap_type = options.get("bitmap_type", self.bitmap_default)
        texture_node = self._create_texture_node(bitmap_type, file_path, context)
        with contextlib.ExitStack() as stack:
            stack.enter_context(ensure_sme_editor_active())
            active_view_number = rt.sme.ActiveView
            current_sme_view = get_target_sme_view(active_view_number)
            view_node = current_sme_view.createNode(texture_node, rt.Point2(0, 0))
            view_node.name = f"{namespace}:{name}"

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
        sme_view_number = int(container["sme_view_number"])
        with contextlib.ExitStack() as stack:
            stack.enter_context(ensure_sme_editor_active())
            current_sme_view = get_target_sme_view(sme_view_number)
            view_node = get_view_node_from_sme_view(
                current_sme_view, view_node_name
            )
            texture_node = view_node.reference

            if find_plugins("vray") and (
                rt.classOf(texture_node) == getattr(rt, "VRayBitmap", None)
            ):
                texture_node.fileName = file_path
            elif rt.classOf(texture_node) == rt.OSLMap:
                texture_node.Filename = file_path
                self._set_udim(context, texture_node)
                texture_node.Filename_ColorSpace = self._get_colorspace(context)
            else:
                raise LoadError(
                    f"Unsupported texture node type: {rt.classOf(texture_node)}"
                )

        imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        view_node_name = container["view_node"]
        sme_view_number = int(container["sme_view_number"])
        with contextlib.ExitStack() as stack:
            stack.enter_context(ensure_sme_editor_active())
            current_sme_view = get_target_sme_view(sme_view_number)
            view_node = get_view_node_from_sme_view(
                current_sme_view, view_node_name
            )
            stack.enter_context(
                maintained_sme_view_nodes_selection(
                    current_sme_view, view_node.reference
                )
            )
            current_sme_view.DeleteSelection()

        container_node = rt.GetNodeByName(container["instance_node"])
        rt.Delete(container_node)

    def _set_udim(self, context, texture_node):
        """Return UDIM list for the file to load.

        Retrieves the UDIM list from the publish data if available.
        This function is not fully working due to the limitations of
        OSLBitmap2 requires users to choose the specific UDIM tile manually
        by dialog.  For now, it helps the users to identify the published
        path of the UDIM textures. Users need to reload the texture again to
        set up the UDIM token.

        Returns:
            list or None: The UDIM list or None if not available.

        """
        repre_context = context["representation"]["context"]
        udims = repre_context.get("udim", [])
        texture_node.UDIM = bool(udims)
        texture_node.LoadUDIM = self.filepath_from_context(context)

    def _get_colorspace(self, context):
        """Return colorspace of the file to load.

        Retrieves the explicit colorspace from the publish. If no colorspace
        data is stored with published content then project imageio settings
        are used to make an assumption of the colorspace based on the file
        rules. If no file rules match then None is returned.

        Returns:
            str or None: The colorspace of the file or None if not detected.

        """
        representation = context["representation"]
        colorspace_data = representation.get("data", {}).get("colorspaceData")
        if colorspace_data:
            return colorspace_data["colorspace"]

        # Assume colorspace from filepath based on project settings
        project_name = context["project"]["name"]
        host_name = get_current_host_name()
        project_settings = get_project_settings(project_name)

        config_data = get_current_context_imageio_config_preset(
            project_settings=project_settings
        )

        # Ignore if host imageio is not enabled
        if not config_data:
            return None

        file_rules = get_imageio_file_rules(
            project_name, host_name,
            project_settings=project_settings
        )

        path = self.filepath_from_context(context)
        return get_imageio_file_rules_colorspace_from_filepath(
            path,
            host_name,
            project_name,
            config_data=config_data,
            file_rules=file_rules,
            project_settings=project_settings
        )
