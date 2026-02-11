# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
from ayon_max.api.plugin import MaxCreator


class CreateRedshiftProxy(MaxCreator):
    identifier = "io.ayon.creators.max.redshiftproxy"
    label = "Redshift Proxy"
    product_base_type = "redshiftproxy"
    product_type = product_base_type
    icon = "gear"
