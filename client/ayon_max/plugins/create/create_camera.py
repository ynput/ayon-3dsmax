# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
from ayon_max.api.plugin import MaxCreator


class CreateCamera(MaxCreator):
    """Creator plugin for Camera."""
    identifier = "io.ayon.creators.max.camera"
    label = "Camera"
    product_base_type = "camera"
    product_type = product_base_type
    icon = "gear"
