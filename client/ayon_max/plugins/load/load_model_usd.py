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
    label = "Load Model (USD)"
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
        folder_name = context["folder"]["name"]
        namespace = unique_namespace(
            name + "_",
            prefix=f"{folder_name}_",
            suffix="_",
        )
        # create "missing" container for obj import
        selections = rt.GetCurrentSelection()
        # get current selection
        for selection in selections:
            selection.name = f"{namespace}:{selection.name}"

        return containerise(
            name, selections, context,
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
        for prev_obj in prev_objects:
            if rt.isValidNode(prev_obj):
                rt.Delete(prev_obj)

        import_options = rt.USDImporter.CreateOptions()
        base_filename = os.path.basename(path)
        _, ext = os.path.splitext(base_filename)
        log_filepath = path.replace(ext, "txt")

        rt.LogPath = log_filepath
        rt.LogLevel = rt.Name("info")
        rt.USDImporter.importFile(
            path, importOptions=import_options)

        # get current selection
        selections = rt.GetCurrentSelection()
        for selection in selections:
            selection.name = f"{namespace}:{selection.name}"
            selection_transform = f"{selection.name}.transform"
            if selection_transform in transform_data.keys():
                selection.pos = transform_data[selection_transform] or 0
                selection.rotation = transform_data[
                    f"{selection.name}.rotation"] or 0
                selection.scale = transform_data[
                    f"{selection.name}.scale"] or 0
        update_custom_attribute_data(node, selections)
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
