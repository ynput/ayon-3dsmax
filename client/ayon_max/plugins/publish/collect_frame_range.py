# -*- coding: utf-8 -*-
import pyblish.api
from pymxs import runtime as rt


class CollectFrameRange(pyblish.api.InstancePlugin):
    """Collect Frame Range."""

    order = pyblish.api.CollectorOrder + 0.011
    label = "Collect Frame Range"
    hosts = ['max']
    families = ["camera", "maxrender",
                "pointcache", "pointcloud",
                "review", "tycache",
                "tyspline", "redshiftproxy",
                "vdb"]

    def process(self, instance):
        if instance.data["productType"] == "maxrender":
            instance.data["frameStartHandle"] = int(rt.rendStart)
            instance.data["frameEndHandle"] = int(rt.rendEnd)

        elif instance.data["family"] in {"tycache", "tyspline"}:
            operator = instance.data["operator"]
            instance.data["frameStartHandle"] = rt.getProperty(operator, "frameStart")
            instance.data["frameEndHandle"] = rt.getProperty(operator, "frameEnd")
        elif instance.data["productType"] == "vdb" and instance.data.get("is_tyflow", False):
            operator = instance.data["operator"]
            instance.data["frameStartHandle"] = rt.getProperty(operator, "timingIntervalStart")
            instance.data["frameEndHandle"] = rt.getProperty(operator, "timingIntervalEnd")
        else:
            instance.data["frameStartHandle"] = int(rt.animationRange.start)
            instance.data["frameEndHandle"] = int(rt.animationRange.end)
