import os

from pymxs import runtime as rt
from ayon_core.pipeline.load import LoadError
from ayon_max.api import lib
from ayon_max.api.lib import (
    unique_namespace,
    get_namespace,
    object_transform_set,
    get_plugins
)
from ayon_max.api.lib import maintained_selection
from ayon_max.api.pipeline import (
    containerise,
    get_previous_loaded_object,
    update_custom_attribute_data,
    remove_container_data
)
from ayon_core.pipeline import load


class ModelUSDLoader(load.LoaderPlugin):
    """Loading model with the USD loader."""

    product_types = {"model"}
    label = "Load Model(USD)"
    representations = {"usda"}
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        # asset_filepath
        plugin_info = get_plugins()
        if "usdimport.dli" not in plugin_info:
            raise LoadError("No USDImporter loaded/installed in Max..")
        filepath = os.path.normpath(self.filepath_from_context(context))
        import_options = rt.USDImporter.CreateOptions()
        base_filename = os.path.basename(filepath)
        _, ext = os.path.splitext(base_filename)
        log_filepath = filepath.replace(ext, "txt")

        rt.LogPath = log_filepath
        rt.LogLevel = rt.Name("info")
        rt.USDImporter.importFile(filepath,
                                  importOptions=import_options)
        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )
        asset = rt.GetNodeByName(name)
        usd_objects = []

        for usd_asset in asset.Children:
            usd_asset.name = f"{namespace}:{usd_asset.name}"
            usd_objects.append(usd_asset)

        asset_name = f"{namespace}:{name}"
        asset.name = asset_name
        # need to get the correct container after renamed
        asset = rt.GetNodeByName(asset_name)
        usd_objects.append(asset)

        return containerise(
            name, usd_objects, context,
            namespace, loader=self.__class__.__name__)

    def update(self, container, context):
        repre_entity = context["representation"]
        path = os.path.normpath(self.filepath_from_context(context))
        node_name = container["instance_node"]
        node = rt.GetNodeByName(node_name)
        namespace, name = get_namespace(node_name)
        node_list = get_previous_loaded_object(node)
        rt.Select(node_list)
        prev_objects = [sel for sel in rt.GetCurrentSelection()
                        if sel != rt.Container
                        and sel.name != node_name]
        transform_data = object_transform_set(prev_objects)
        for n in prev_objects:
            rt.Delete(n)

        import_options = rt.USDImporter.CreateOptions()
        base_filename = os.path.basename(path)
        _, ext = os.path.splitext(base_filename)
        log_filepath = path.replace(ext, "txt")

        rt.LogPath = log_filepath
        rt.LogLevel = rt.Name("info")
        rt.USDImporter.importFile(
            path, importOptions=import_options)

        asset = rt.GetNodeByName(name)
        usd_objects = []
        for children in asset.Children:
            children.name = f"{namespace}:{children.name}"
            usd_objects.append(children)
            children_transform = f"{children}.transform"
            if children_transform in transform_data.keys():
                children.pos = transform_data[children_transform] or 0
                children.scale = transform_data[
                    f"{children}.scale"] or 0

        asset.name = f"{namespace}:{asset.name}"
        usd_objects.append(asset)
        update_custom_attribute_data(node, usd_objects)
        with maintained_selection():
            rt.Select(node)

        lib.imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        from pymxs import runtime as rt
        node = rt.GetNodeByName(container["instance_node"])
        remove_container_data(node)
