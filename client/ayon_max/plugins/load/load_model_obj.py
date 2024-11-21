import os

from ayon_max.api import lib
from ayon_max.api.lib import (
    unique_namespace,
    get_namespace,
    maintained_selection,
    object_transform_set
)
from ayon_max.api.pipeline import (
    containerise,
    get_previous_loaded_object,
    update_custom_attribute_data,
    remove_container_data
)
from ayon_core.pipeline import get_representation_path, load


class ObjLoader(load.LoaderPlugin):
    """Obj Loader."""

    product_types = {"model"}
    representations = {"obj"}
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        from pymxs import runtime as rt

        filepath = os.path.normpath(self.filepath_from_context(context))
        self.log.debug("Executing command to import..")

        rt.Execute(f'importFile @"{filepath}" #noPrompt using:ObjImp')

        namespace = unique_namespace(
            name + "_",
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
        from pymxs import runtime as rt

        repre_entity = context["representation"]
        path = os.path.normpath(self.filepath_from_context(context))
        node_name = container["instance_node"]
        node = rt.getNodeByName(node_name)
        namespace, _ = get_namespace(node_name)
        node_list = get_previous_loaded_object(node)
        rt.Select(node_list)
        previous_objects = rt.GetCurrentSelection()
        transform_data = object_transform_set(previous_objects)
        for prev_obj in previous_objects:
            if rt.isValidNode(prev_obj):
                rt.Delete(prev_obj)

        rt.Execute(f'importFile @"{path}" #noPrompt using:ObjImp')
        # get current selection
        selections = rt.GetCurrentSelection()
        for selection in selections:
            selection.name = f"{namespace}:{selection.name}"
            selection_transform = f"{selection}.transform"
            if selection_transform in transform_data.keys():
                selection.pos = transform_data[selection_transform] or 0
                selection.scale = transform_data[
                    f"{selection}.scale"] or 0
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
