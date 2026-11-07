# -*- coding: utf-8 -*-
"""Creator plugin for creating TyFlow."""
from ayon_max.api import plugin


class CreateTyFlow(plugin.MaxCacheCreator):
    """Creator plugin for TyFlow."""
    identifier = "io.ayon.creators.max.tyflow"
    label = "TyFlow"
    product_base_type = "tyflow"
    product_type = product_base_type
    icon = "gear"


class CreateTyVDB(plugin.MaxTyflowVDBCacheCreator):
    """Creator plugin for TyFlow VDB."""
    identifier = "io.ayon.creators.max.vdbcache"
    label = "VDB (TyFlow)"
    product_base_type = "vdbcache"
    product_type = product_base_type
    icon = "gear"

    def get_published_families(self):
        return ["vdbcache", "tyflow_vdb"]
