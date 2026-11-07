# -*- coding: utf-8 -*-
"""Creator plugin for model."""
from ayon_max.api.plugin import MaxCreator


class CreateModel(MaxCreator):
    """Creator plugin for Model."""
    identifier = "io.ayon.creators.max.model"
    label = "Model"
    product_base_type = "model"
    product_type = product_base_type
    icon = "gear"
