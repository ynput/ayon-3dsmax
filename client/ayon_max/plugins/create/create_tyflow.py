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
    """Creator plugin for TyFlow VDB.

    The publisher 'Variant' value is used to distinguish multiple VDB
    containers in the same context. The product name template may contain
    the '{variant}' and '{operator}' keys, e.g.
    '{folder[name]}_{task[name]}_{variant}_vdbcache_{operator}'.

    The '{operator}' key is optional: when it is not in the template, the
    operator name is appended to the product name during collection.
    """

    # The identifier is independent of the product type and must stay
    #   stable; the published product type is 'vdbcache'.
    identifier = "io.ayon.creators.max.vdb"
    label = "VDB (TyFlow)"
    # Products are regular 'vdbcache' products. The TyFlow specific family
    #   is added to each product during collection (based on the creator
    #   identifier), so the container instance itself is not published as
    #   a TyFlow VDB product.
    product_base_type = "vdbcache"
    product_type = product_base_type
    icon = "gear"

    def get_dynamic_data(self, *args, **kwargs):
        """Keep the operator part of the product name unfilled.

        Single VDB container creates one product per TyFlow 'Export VDB'
        operator, so the operator is not known when the instance is created.
        The '{operator}' key is filled in by ``CollectTyFlowVDBData`` for
        each created product.
        """
        return {
            "operator": "{operator}",
        }
