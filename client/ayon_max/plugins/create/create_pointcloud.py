# -*- coding: utf-8 -*-
"""Creator plugin for creating point cloud."""
from ayon_max.api.plugin import MaxCreator


class CreatePointCloud(MaxCreator):
    """Creator plugin for Point Clouds."""
    identifier = "io.ayon.creators.max.pointcloud"
    label = "Point Cloud"
    product_base_type = "pointcloud"
    product_type = product_base_type
    icon = "gear"
