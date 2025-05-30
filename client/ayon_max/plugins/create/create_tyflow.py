# -*- coding: utf-8 -*-
"""Creator plugin for creating TyFlow."""
from ayon_max.api import plugin


class CreateTyFlow(plugin.MaxCacheCreator):
    """Creator plugin for TyFlow."""
    identifier = "io.ayon.creators.max.tyflow"
    label = "TyFlow"
    product_type = "tyflow"
    icon = "gear"
