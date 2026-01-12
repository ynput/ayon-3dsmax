# -*- coding: utf-8 -*-
"""Collect Render"""
import os
import pyblish.api

from pymxs import runtime as rt
from ayon_core.pipeline.publish import KnownPublishError
from ayon_max.api import colorspace
from ayon_max.api.lib import get_max_version, get_current_renderer
from ayon_max.api.lib_rendersettings import RenderSettings
from ayon_max.api.lib_renderproducts import RenderProducts


def get_camera_from_node(members):
    """Get camera from instance members."""
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
    hosts = ['max']
    families = ["maxrender"]

    def process(self, instance):
        context = instance.context
        folder = rt.maxFilePath
        file = rt.maxFileName
        current_file = os.path.join(folder, file)
        filename = os.path.splitext(file)[0]
        self.log.debug(f"Current: {filename}")
        filepath = current_file.replace("\\", "/")
        context.data['currentFile'] = current_file
        renderer_class = get_current_renderer()
        renderer = str(renderer_class).split(":")[0]

        files_by_aov = RenderProducts().get_beauty(instance.name, renderer, filename)
        aovs = RenderProducts().get_aovs(instance.name, filename)
        files_by_aov.update(aovs)

        camera = rt.viewport.GetCamera()
        camera_list = get_camera_from_node(instance.data.get("members"))
        if camera_list:
            camera = camera_list[-1]

        instance.data["cameras"] = [camera.name] if camera else None        # noqa

        if instance.data.get("multiCamera"):
            cameras = instance.data.get("members")
            if not cameras:
                raise KnownPublishError("There should be at least"
                                        " one renderable camera in container")
            sel_cam = get_camera_from_node(cameras)

            container_name = instance.data.get("instance_node")
            outputs = RenderSettings().batch_render_layer(
                container_name, sel_cam, filename
            )

            instance.data["cameras"] = sel_cam

            files_by_aov = RenderProducts().get_multiple_beauty(
                outputs, sel_cam)
            aovs = RenderProducts().get_multiple_aovs(
                outputs, sel_cam)
            files_by_aov.update(aovs)

        if "expectedFiles" not in instance.data:
            instance.data["expectedFiles"] = list()
            instance.data["files"] = list()
            instance.data["expectedFiles"].append(files_by_aov)
            instance.data["files"].append(files_by_aov)
        img_format = RenderProducts().image_format()
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
        product_type = "maxrender"
        render_dir = os.path.dirname(rt.rendOutputFilename)
        # also need to get the render dir for conversion
        data = {
            "folderPath": instance.data["folderPath"],
            "productName": str(instance.name),
            "publish": True,
            "original_workfile_pattern": render_dir.rsplit("\\")[-1],
            "maxversion": str(get_max_version()),
            "imageFormat": img_format,
            "productType": product_type,
            "family": product_type,
            "families": [product_type],
            "renderer": renderer,
            "source": filepath,
            "plugin": "3dsmax",
            "frameStart": instance.data["frameStartHandle"],
            "frameEnd": instance.data["frameEndHandle"],
            "farm": True
        }
        instance.data.update(data)
        self.log.debug(instance.data)
        # TODO: this should be unified with maya and its "multipart" flag
        #       on instance.
        if renderer == "Redshift_Renderer":
            instance.data.update(
                {"separateAovFiles": rt.Execute(
                    "renderers.current.separateAovFiles")})

        self.log.info("data: {0}".format(data))
