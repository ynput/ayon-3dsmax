# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
import os

from ayon_core.lib import BoolDef, EnumDef
from ayon_core.pipeline import CreatorError, registered_host

from ayon_max.api.plugin import MaxCreator
from ayon_max.api.lib_rendersettings import RenderSettings

from pymxs import runtime as rt


class CreateRender(MaxCreator):
    """Creator plugin for Renders."""
    identifier = "io.ayon.creators.max.render"
    label = "Render"
    product_base_type = "maxrender"
    product_type = product_base_type
    icon = "gear"

    render_target = "farm"

    def create(self, product_name, instance_data, pre_create_data):
        host = registered_host()
        current_file = host.get_current_workfile()
        if not current_file:
            raise CreatorError(
                "Please save the scene before creating render instance"
            )
        file = rt.maxFileName
        filename, _ = os.path.splitext(file)
        instance_data["AssetName"] = filename
        instance_data["multiCamera"] = pre_create_data.get("multi_cam")
        num_of_renderlayer = rt.batchRenderMgr.numViews
        if num_of_renderlayer > 0:
            rt.batchRenderMgr.DeleteView(num_of_renderlayer)

        container = rt.getNodeByName(product_name)
        product_base_type = instance_data["productBaseType"]
        # check if there is existing render instance
        if container and product_name.startswith(product_base_type):
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
            output_dir = os.path.dirname(rt.rendOutputFilename)
            RenderSettings().batch_render_layers_by_multi_camera(
                container_name, output_dir, selected_nodes_name
            )

    def get_instance_attr_defs(self):
        render_target_items: dict[str, str] = {
            "local": "Local machine rendering",
            "local_no_render": "Use existing frames (local)",
            "farm": "Farm Rendering",
        }
        return [
            EnumDef("render_target",
                    items=render_target_items,
                    label="Render target",
                    default=self.render_target),
        ]

    def get_pre_create_attr_defs(self):
        attrs = super(CreateRender, self).get_pre_create_attr_defs()
        return attrs + [
            BoolDef("multi_cam",
                    label="Multiple Cameras Submission",
                    default=False),
        ]
