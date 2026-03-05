# -*- coding: utf-8 -*-
"""Collect instance members."""
import pyblish.api
from pymxs import runtime as rt
from ayon_max.api.lib import get_ayon_data


FILTER_PRODUCT_BASE_TYPES = {
     "workfile", "tyflow", "tycache",
     "tyspline", "renderpreset", "look"
}


class CollectMembers(pyblish.api.InstancePlugin):
    """Collect Set Members."""

    order = pyblish.api.CollectorOrder + 0.01
    label = "Collect Instance Members"
    hosts = ['max']

    def process(self, instance):
        if instance.data["productBaseType"] in FILTER_PRODUCT_BASE_TYPES:
                self.log.debug(
                    "Skipping Collecting Members for "
                    f"{instance.data['productBaseType']} product base type."
                )
                return

        elif instance.data.get("instance_node"):
            container = rt.GetNodeByName(instance.data["instance_node"])
            container_modifier = container.modifiers[0]
            ayon_data = get_ayon_data(container_modifier)
            instance.data["members"] = [
                member.node for member in ayon_data.all_handles
            ]
