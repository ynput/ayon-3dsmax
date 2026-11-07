# -*- coding: utf-8 -*-
"""Creator plugin for creating raw max scene."""
from ayon_max.api.plugin import MaxCreator


class CreateMaxScene(MaxCreator):
    """Creator plugin for 3ds max scenes."""
    identifier = "io.ayon.creators.max.maxScene"
    label = "Max Scene"
    product_base_type = "maxScene"
    product_type = product_base_type
    icon = "gear"
