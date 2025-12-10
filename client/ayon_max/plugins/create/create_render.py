# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
import os
from ayon_max.api import plugin
from ayon_core.lib import BoolDef
from ayon_core.pipeline import CreatorError
from ayon_max.api.lib_rendersettings import RenderSettings

from pymxs import runtime as rt


class CreateRender(plugin.MaxCreator):
    """Creator plugin for Renders."""
    identifier = "io.openpype.creators.max.render"
    label = "Render"
    product_type = "maxrender"
    product_base_type = "maxrender"
    icon = "gear"

    settings_category = "max"

    def create(self, product_name, instance_data, pre_create_data):
        file = rt.maxFileName
        filename, _ = os.path.splitext(file)
        instance_data["AssetName"] = filename
        instance_data["multiCamera"] = pre_create_data.get("multi_cam")
        num_of_renderlayer = rt.batchRenderMgr.numViews
        if num_of_renderlayer > 0:
            rt.batchRenderMgr.DeleteView(num_of_renderlayer)

        container = rt.getNodeByName(product_name)
        product_type = instance_data["productType"]
        # check if there is existing render instance
        if container and product_name.startswith(product_type):
            raise CreatorError("Render instance already exists")

        instance = super(CreateRender, self).create(
            product_name,
            instance_data,
            pre_create_data)

        container_name = instance.data.get("instance_node")
        # set output paths for rendering(mandatory for deadline)
        RenderSettings().render_output(container_name)
        # TODO: create multiple camera options
        if self.selected_nodes:
            selected_nodes_name = []
            for sel in self.selected_nodes:
                name = sel.name
                selected_nodes_name.append(name)
            RenderSettings().batch_render_layer(
                container_name, filename,
                selected_nodes_name)

    def get_pre_create_attr_defs(self):
        attrs = super(CreateRender, self).get_pre_create_attr_defs()
        return attrs + [
            BoolDef("multi_cam",
                    label="Multiple Cameras Submission",
                    default=False),
        ]
