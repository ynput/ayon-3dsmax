import os
import clique

from ayon_core.pipeline import (
    load,
    get_representation_path
)
from ayon_core.pipeline.load import LoadError
from ayon_max.api.pipeline import (
    containerise,
    update_custom_attribute_data,
    get_previous_loaded_object,
    remove_container_data
)
from ayon_max.api import lib
from ayon_max.api.lib import (
    unique_namespace,
    get_plugins
)


class RedshiftProxyLoader(load.LoaderPlugin):
    """Load rs files with Redshift Proxy"""

    label = "Load Redshift Proxy"
    product_types = {"redshiftproxy"}
    representations = {"rs"}
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        from pymxs import runtime as rt
        plugin_info = get_plugins()
        if "redshift4max.dlr" not in plugin_info:
            raise LoadError("Redshift not loaded/installed in Max..")
        filepath = self.filepath_from_context(context)
        rs_proxy = rt.RedshiftProxy()
        rs_proxy.file = filepath
        files_in_folder = os.listdir(os.path.dirname(filepath))
        collections, remainder = clique.assemble(files_in_folder)
        if collections:
            rs_proxy.is_sequence = True

        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )
        rs_proxy.name = f"{namespace}:{rs_proxy.name}"

        return containerise(
            name, [rs_proxy], context,
            namespace, loader=self.__class__.__name__)

    def update(self, container, context):
        from pymxs import runtime as rt

        repre_entity = context["representation"]
        path = get_representation_path(repre_entity)
        node = rt.getNodeByName(container["instance_node"])
        node_list = get_previous_loaded_object(node)
        rt.Select(node_list)
        update_custom_attribute_data(
            node, rt.Selection)
        for proxy in rt.Selection:
            proxy.file = path

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
