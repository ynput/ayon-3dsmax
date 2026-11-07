# -*- coding: utf-8 -*-
"""Creator plugin for creating pointcache alembics."""
from ayon_max.api.plugin import MaxCreator


class CreatePointCache(MaxCreator):
    """Creator plugin for Point caches."""
    identifier = "io.ayon.creators.max.pointcache"
    label = "Point Cache"
    product_base_type = "pointcache"
    product_type = product_base_type
    icon = "gear"
