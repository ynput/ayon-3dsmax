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
    # Products are regular 'vdbcache' products. The TyFlow specific family
    #   is added to each product during collection (based on the creator
    #   identifier), so the container instance itself is not published as
    #   a TyFlow VDB product.
    product_base_type = "vdbcache"
    product_type = product_base_type
    icon = "gear"

    def get_dynamic_data(
        self,
        project_name,
        folder_entity,
        task_entity,
        variant,
        host_name,
        instance=None,
        project_entity=None,
        product_type=None,
    ):
        """Keep the operator part of the product name unfilled.

        Single VDB container creates one product per TyFlow 'Export VDB'
        operator, so the operator is not known when the instance is created.
        The '{operator}' key is filled in by ``CollectTyFlowVDBData`` for
        each created product.
        """
        return {
            "operator": "{operator}",
        }
