from ayon_core.pipeline import load
from ayon_max.api.pipeline import containerise, remove_container_data

from ayon_max.api.lib import imprint, unique_namespace

from pymxs import runtime as rt


class LoadMatlib(load.LoaderPlugin):
    """Load material library files with Material Library"""

    label = "Load Material Library"
    product_base_types = {"matlib"}
    product_types = product_base_types
    representations = {"mat"}
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name, namespace, data):
        """Load the material library file into the scene and containerise it."""
        file_path = self.filepath_from_context(context)
        folder_name = context["folder"]["name"]
        namespace = unique_namespace(
            name + "_",
            prefix=f"{folder_name}_",
            suffix="_",
        )
        rt.sme.OpenMtlLib(file_path)
        return containerise(
            name,
            [],
            context,
            namespace=namespace,
            loader=self.__class__.__name__,
            additional_data={"matlib_filepath": file_path}
        )

    def update(self, container, context):
        """Update the material library file path in the container."""
        # Close the previous filepath
        prev_filepath = container["matlib_filepath"]
        rt.sme.CloseMtlLib(prev_filepath)
        # Open the updated filepath
        updated_filepath = self.filepath_from_context(context)
        rt.sme.OpenMtlLib(updated_filepath)
        repre_entity = context["representation"]
        imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"],
            "matlib_filepath": updated_filepath,
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        """Remove the material library from the scene and clean up the container."""
        matlib_filepath = container["matlib_filepath"]
        if matlib_filepath:
            rt.sme.CloseMtlLib(matlib_filepath)
        remove_container_data(container["instance_node"])
