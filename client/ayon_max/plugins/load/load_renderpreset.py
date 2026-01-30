import os
from ayon_core.pipeline import load
from ayon_core.pipeline.load import LoadError
from ayon_max.api.pipeline import containerise, remove_container_data

from ayon_max.api import lib

from pymxs import runtime as rt


class RenderPresetLoader(load.LoaderPlugin):
    """Load rps files with Render Preset"""

    label = "Load Render Preset"
    product_types = {"renderpreset"}
    representations = {"rps"}
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        if not rt.renderSceneDialog.isOpen():
            raise LoadError(
                "Render Scene Dialog is not open. "
                "Make sure it is open before loading render presets."
            )
        # adding os.path.normpath to fix
        # special FileName typeError in 3dsMax
        filepath = os.path.normpath(self.filepath_from_context(context))
        folder_name = context["folder"]["name"]
        namespace = lib.unique_namespace(
            name + "_",
            prefix=f"{folder_name}_",
            suffix="_",
        )
        rt.renderpresets.LoadAll(0, filepath)
        return containerise(
            name, [], context,
            namespace, loader=self.__class__.__name__)

    def update(self, container, context):
        if not rt.renderSceneDialog.isOpen():
            raise LoadError(
                "Render Scene Dialog is not open. "
                "Make sure it is open before loading render presets."
            )
        # adding os.path.normpath to fix
        # special FileName typeError in 3dsMax
        path = os.path.normpath(self.filepath_from_context(context))
        rt.renderpresets.LoadAll(0, path)
        lib.imprint(container["instance_node"], {
            "representation": context["representation"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = rt.GetNodeByName(container["instance_node"])
        remove_container_data(node)
