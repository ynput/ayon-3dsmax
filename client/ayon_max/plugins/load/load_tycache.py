import os
from pymxs import runtime as rt
from ayon_max.api import lib, maintained_selection
from ayon_max.api.lib import (
    unique_namespace,

)
from ayon_max.api.pipeline import (
    containerise,
    get_previous_loaded_object,
    update_custom_attribute_data,
    remove_container_data
)
from ayon_core.pipeline import load, LoadError


class TyCacheLoader(load.LoaderPlugin):
    """TyCache Loader."""

    product_types = {"tycache"}
    representations = {"tyc"}
    order = -8
    icon = "code-fork"
    color = "green"

    def load(self, context, name=None, namespace=None, data=None):
        """Load tyCache"""
        filepath = os.path.normpath(self.filepath_from_context(context))

        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )
        obj = self.load_tycache(filepath, namespace)

        return containerise(
            name, [obj], context,
            namespace, loader=self.__class__.__name__)

    def update(self, container, context):
        """update the container"""
        repre_entity = context["representation"]
        path = os.path.normpath(self.filepath_from_context(context))
        node = rt.GetNodeByName(container["instance_node"])
        node_list = get_previous_loaded_object(node)
        update_custom_attribute_data(node, node_list)
        with maintained_selection():
            self.load_tycache(path, node_list)
        lib.imprint(container["instance_node"], {
            "representation": repre_entity["id"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        """remove the container"""
        node = rt.GetNodeByName(container["instance_node"])
        remove_container_data(node)
        rt.Delete(node)

    def load_tycache(self, filepath, namespace):
        obj = rt.tyCache()
        obj.filename = filepath
        obj.name = f"{namespace}:{obj.name}"
        return obj

    def update_tycache(self, path, node_list):
        for tyc in node_list:
            tyc.filename = path

class TySplineCacheLoader(TyCacheLoader):
    """TyCache(Spline) Loader."""

    product_types = {"tyspline"}
    representations = {"tyc"}
    order = -8
    icon = "code-fork"
    color = "green"

    def load_tycache(self, filepath, namespace):
        obj = rt.tyCache()
        obj.filename = filepath
        tySplineCache_modifier = rt.tySplineCache()
        rt.addModifier(obj, tySplineCache_modifier)
        obj.name = f"{namespace}:{obj.name}"
        return obj


class TyCacheModifierLoader(TyCacheLoader):
    """Load TyCache with Modifier """

    representations = {"tycm"}
    order = -8
    icon = "code-fork"
    color = "green"

    def load_tycache(self, filepath, namespace):
        if int(rt.tyFlow_version()) < 112000:
            raise LoadError(
                "This loader only works in TyFlow v1.12. "
                "Please update your TyFlow! ")
        obj = rt.Container()
        tyc_modifier = rt.tyCachemodifier()
        # switch the tyCache modifier mode
        # to load/save the cache in tyc format
        tyc_modifier.mode = 1
        tyc_modifier.filename = filepath
        rt.addModifier(obj, tyc_modifier)
        obj.name = f"{namespace}:{tyc_modifier.name}"
        return obj

    def update_tycache(self, path, node_list):
        for node in node_list:
            for modifier in node.modifiers:
                if rt.Classof(modifier) == "tyCachemodifier":
                    modifier.filename = path
