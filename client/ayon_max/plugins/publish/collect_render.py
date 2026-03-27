# -*- coding: utf-8 -*-
"""Collect Render"""
from __future__ import annotations
import os
import pyblish.api
import ayon_api
from typing import Dict, Any

from pymxs import runtime as rt
from ayon_core.pipeline.publish import KnownPublishError
from ayon_max.api import colorspace
from ayon_max.api.lib import (
    get_max_version,
    get_current_renderer,
    get_vray_settings,
    get_multipass_setting,
)
from ayon_max.api.lib_rendersettings import RenderSettings
from ayon_max.api.lib_renderproducts import RenderProducts


def get_cameras_from_node(members) -> list:
    """Get camera from instance members.

    Args:
        members (list): The list of instance members.

    Returns:
        list: A list of camera objects.
    """
    cameras = []
    for member in members:
        if rt.classOf(member) in rt.Camera.classes:
            cameras.append(member)
        if hasattr(member, "children"):
            for child in member.children:
                if rt.classOf(child) in rt.Camera.classes:
                    cameras.append(child)
    return cameras


class CollectRender(pyblish.api.InstancePlugin):
    """Collect Render for Deadline"""

    order = pyblish.api.CollectorOrder + 0.02
    label = "Collect 3dsmax Render Layers"
    hosts = ["max"]
    families = ["maxrender"]
    settings_category = "max"

    # Settings
    sync_workfile_version = False

    def process(self, instance):
        context = instance.context
        folder = rt.maxFilePath
        file = rt.maxFileName
        current_file = os.path.join(folder, file)
        filename = os.path.splitext(file)[0]
        self.log.debug(f"Current: {filename}")
        filepath = current_file.replace("\\", "/")
        context.data['currentFile'] = current_file
        renderer = get_current_renderer()
        renderer_name = str(renderer).split(":")[0]
        renderproducts = RenderProducts(context.data["project_settings"])
        img_format = renderproducts.image_format()
        render_output = self.get_render_output(
            renderer,
            renderer_name,
            img_format,
            context.data["project_settings"]
        )
        render_dir = os.path.dirname(render_output)
        files_by_aov: Dict[str, list[str]] = renderproducts.get_render_products()


        camera = rt.viewport.GetCamera()
        camera_list = get_cameras_from_node(instance.data.get("members"))
        if camera_list:
            camera = camera_list[-1]

        instance.data["cameras"] = [camera.name] if camera else None        # noqa

        if instance.data.get("multiCamera"):
            cameras = instance.data.get("members")
            if not cameras:
                raise KnownPublishError("There should be at least"
                                        " one renderable camera in container")

            sel_cam = [camera.name for camera in get_cameras_from_node(cameras)]

            container_name = instance.data.get("instance_node")
            outputs = RenderSettings().batch_render_layers_by_multi_camera(
                container_name, render_dir, sel_cam
            )

            instance.data["cameras"] = sel_cam

            files_by_aov = renderproducts.get_multiple_render_products(
                outputs, sel_cam
            )

        if "expectedFiles" not in instance.data:
            instance.data["expectedFiles"] = list()
            instance.data["files"] = list()
            instance.data["expectedFiles"].append(files_by_aov)
            instance.data["files"].append(files_by_aov)
        self.log.debug(f"Files by AOV: {files_by_aov}")
        # OCIO config not support in
        # most of the 3dsmax renderers
        # so this is currently hard coded
        # TODO: add options for redshift/vray ocio config
        instance.data["colorspaceConfig"] = ""
        instance.data["colorspaceDisplay"] = "sRGB"
        instance.data["colorspaceView"] = "ACES 1.0 SDR-video"

        if int(get_max_version()) >= 2024:
            colorspace_mgr = rt.ColorPipelineMgr      # noqa
            display = next(
                (display for display in colorspace_mgr.GetDisplayList()))
            view_transform = next(
                (view for view in colorspace_mgr.GetViewList(display)))
            instance.data["colorspaceConfig"] = colorspace_mgr.OCIOConfigPath
            instance.data["colorspaceDisplay"] = display
            instance.data["colorspaceView"] = view_transform

        instance.data["renderProducts"] = colorspace.ARenderProduct()
        instance.data["publishJobState"] = "Suspended"
        instance.data["attachTo"] = []

        product_base_type = "maxrender"

        # Keep custom product type only if is not the same
        #   as product base type
        product_type = instance.data["productType"]
        if product_type == instance.data["productBaseType"]:
            product_type = product_base_type

        creator_attribute = instance.data.get("creator_attributes", {})
        farm_render: bool = (
            creator_attribute.get("render_target", "farm") == "farm"
        )
        self._precollect_required_data(instance)

        # also need to get the render dir for conversion
        data = {
            "folderPath": instance.data["folderPath"],
            "workfile_name": filename,
            "productName": str(instance.name),
            "publish": True,
            "original_workfile_pattern": render_dir.rsplit("\\")[-1],
            "maxversion": str(get_max_version()),
            "imageFormat": img_format,
            "productBaseType": product_base_type,
            "productType": product_type,
            "family": product_base_type,
            "families": [product_base_type],
            "renderer": renderer_name,
            "source": filepath,
            "plugin": "3dsmax",
            "frameStart": instance.data["frameStartHandle"],
            "frameEnd": instance.data["frameEndHandle"],
            "resolutionWidth": rt.renderWidth,
            "resolutionHeight": rt.renderHeight,
            "farm": farm_render
        }

        # sync workfile version
        if self.sync_workfile_version:
            data["version"] = context.data["version"]
            for _instance in context:
                if _instance.data["productBaseType"] == "workfile":
                    _instance.data["version"] = context.data["version"]

        instance.data.update(data)
        # TODO: this should be unified with maya and its "multipart" flag
        #       on instance.
        if renderer_name == "Redshift_Renderer":
            instance.data.update(
                {"separateAovFiles": rt.Execute(
                    "renderers.current.separateAovFiles")})

        self.log.info("data: {0}".format(data))

    def get_render_output(
            self,
            renderer: Any,
            renderer_name: str,
            img_format: str,
            project_settings: Dict
        ) -> str:
        """Get render output path for the given renderer and instance.

        Args:
            renderer (Any, rt.Renderers.current): The renderer to get the
                output path from.
            renderer_name (str): The name of the renderer.
            img_format (str): The image format.
            project_settings (Dict): The project settings.

        Returns:
            str: The render output path.
        """
        if renderer_name == "Redshift_Renderer":
            return rt.rendOutputFilename
        elif renderer_name == "Arnold_Renderer":
            return renderer.AOVManager.outputPath
        elif renderer_name.startswith("V-Ray"):
            vr_settings = get_vray_settings(renderer_name, renderer)
            multipass = get_multipass_setting(renderer, project_settings)
            if multipass and img_format == "exr":
                return vr_settings.output_rawfilename
            else:
                return vr_settings.output_splitfilename
        return rt.rendOutputFilename

    def _precollect_required_data(self, instance: pyblish.api.Instance) -> None:
        """Ensure required data is present.

        Some data may not exist yet in the instance at this point, so we need
        to ensure it is there for certain function calls, like
        `create_instances_for_aov` requiring `taskEntity` in instance data
        if setting `use_legacy_product_names_for_renders` is disabled which is
        usually collected at a later order by `CollectAnatomyInstanceData`.

        Args:
            instance (pyblish.api.Instance): The instance to ensure data for.
        """

        project_name: str = instance.context.data["projectName"]

        # Add folderEntity
        if "folderEntity" not in instance.data:
            self.log.debug("Collecting folder entity for instance...")
            instance.data["folderEntity"] = ayon_api.get_folder_by_path(
                project_name=project_name,
                folder_path=instance.data["folderPath"],
            )
        folder_entity = instance.data["folderEntity"]

        # Add taskEntity
        if "taskEntity" not in instance.data:
            self.log.debug("Collecting task entity for instance...")
            project_name: str = instance.context.data["projectName"]
            instance.data["taskEntity"] = ayon_api.get_task_by_name(
                project_name=project_name,
                task_name=instance.data["task"],
                folder_id=folder_entity["id"],
            )
