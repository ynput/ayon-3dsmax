# -*- coding: utf-8 -*-
import pyblish.api
from pymxs import runtime as rt
from ayon_max.api.lib import get_expected_frames


class CollectFrameRange(pyblish.api.InstancePlugin):
    """Collect Frame Range."""

    order = pyblish.api.CollectorOrder + 0.019
    label = "Collect Frame Range"
    hosts = ['max']
    families = ["camera", "maxrender",
                "pointcache", "pointcloud",
                "review", "tycache",
                "tyspline", "redshiftproxy"]

    def process(self, instance):
        if instance.data["productBaseType"] == "maxrender":
            frame_range = get_expected_frames(instance)
            instance.data["frameStartHandle"] = min(frame_range)
            instance.data["frameEndHandle"] = max(frame_range)
            instance.data["expectedFrameRange"] = frame_range

        elif instance.data["productBaseType"] in {"tycache", "tyspline"}:
            operator = instance.data["operator"]
            instance.data["frameStartHandle"] = rt.getProperty(operator, "frameStart")
            instance.data["frameEndHandle"] = rt.getProperty(operator, "frameEnd")
        else:
            instance.data["frameStartHandle"] = int(rt.animationRange.start)
            instance.data["frameEndHandle"] = int(rt.animationRange.end)
