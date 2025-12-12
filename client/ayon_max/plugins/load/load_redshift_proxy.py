import os

from ayon_core.pipeline import load
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

from pymxs import runtime as rt


class RedshiftProxyLoader(load.LoaderPlugin):
    """Load rs files with Redshift Proxy"""

    label = "Load Redshift Proxy"
    product_types = {"redshiftproxy"}
    representations = {"rs"}
    order = -9
    icon = "code-fork"
    color = "white"

    def load(self, context, name=None, namespace=None, data=None):
        plugin_info = get_plugins()
        if "redshift4max.dlr" not in plugin_info:
            raise LoadError("Redshift not loaded/installed in Max..")
        filepath = self.filepath_from_context(context)
        rs_obj = self._get_redshift_object_type()
        rs_obj.file = filepath

        folder_name = context["folder"]["name"]
        namespace = unique_namespace(
            f"{folder_name}_{name}" + "_",
            suffix="_",
        )
        rs_obj.name = f"{namespace}:{rs_obj.name}"

        return containerise(
            name, [rs_obj], context,
            namespace, loader=self.__class__.__name__)

    def update(self, container, context):
        repre_entity = context["representation"]
        path = os.path.normpath(self.filepath_from_context(context))
        node = rt.getNodeByName(container["instance_node"])
        node_list = get_previous_loaded_object(node)
        rt.Select(node_list)
        update_custom_attribute_data(
            node, rt.Selection)
        for rs_obj in rt.Selection:
            rs_obj.file = path

        lib.imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        node = rt.GetNodeByName(container["instance_node"])
        remove_container_data(node)

    def _get_redshift_object_type(self):
        return rt.RedshiftProxy()


class RedshiftVolumeLoader(RedshiftProxyLoader):
    """Load vdb files with Redshift Volume Grid"""

    label = "Load VDB"
    product_types = {"vdbcache"}
    representations = {"vdb"}
    order = -9
    icon = "code-fork"
    color = "orange"

    def _get_redshift_object_type(self):
        return rt.RedshiftVolumeGrid()
