# -*- coding: utf-8 -*-
"""Creator plugin for creating TyFlow."""
from ayon_max.api.plugin import MaxCacheCreator


class CreateTyFlow(MaxCacheCreator):
    """Creator plugin for TyFlow."""
    identifier = "io.ayon.creators.max.tyflow"
    label = "TyFlow"
    product_base_type = "tyflow"
    product_type = product_base_type
    icon = "gear"
