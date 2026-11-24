# -*- coding: utf-8 -*-
"""Collect TyFlow VDB products from a TyFlow VDB container."""
import copy
import re

import pyblish.api
from pymxs import runtime as rt

from ayon_max.api.lib import get_tyflow_export_operators


class CollectTyFlowVDBData(pyblish.api.InstancePlugin):
    """Create one product per TyFlow 'Export VDB' operator.

    The creator creates a single container instance which holds the list
    of 'Export VDB' operators selected by the artist. This collector turns
    each of the selected operators into a separate publishable product.
    """

    order = pyblish.api.CollectorOrder - 0.45
    label = "Collect TyFlow VDB Data"
    hosts = ["max"]
    families = ["vdbcache"]

    def process(self, instance):
        data = instance.data
        if data.get("creator_identifier") != "io.ayon.creators.max.vdb":
            # Not created by the TyFlow VDB creator.
            return
        if "tyflow_vdb" in data.get("families", []):
            # Product created by this collector, do not process it again.
            return

        # The container instance itself is not a product, skip its
        #   integration even when no product ends up being created.
        data["integrate"] = False

        instance_node = data.get("instance_node")
        if not instance_node:
            self.log.warning(
                "TyFlow VDB instance does not have an instance node. "
                "Skipping product creation."
            )
            return

        container = rt.GetNodeByName(instance_node)
        if container is None:
            self.log.warning(
                "TyFlow VDB instance node '{}' was not found. "
                "Skipping product creation.".format(instance_node)
            )
            return

        vdb_export_names = self._get_vdb_export_names(container)
        if not vdb_export_names:
            self.log.warning(
                "No 'Export VDB' operator is added to the TyFlow VDB "
                "container '{}'. Nothing will be published for this "
                "instance. Add an 'Export VDB' operator in the modifier "
                "panel.".format(instance_node)
            )
            return

        operators = {}
        ambiguous_operator_names = set()
        for operator in get_tyflow_export_operators(
                operator_type="exportVDB"):
            if operator.name in operators:
                ambiguous_operator_names.add(operator.name)
            operators[operator.name] = operator

        product_name_template = data["productName"]
        if not re.search(r"\{operator\}", product_name_template, re.IGNORECASE):
            self.log.debug(
                f"Product name '{product_name_template}' does not contain "
                "the '{operator}' key, the operator name is appended to "
                "the product name."
            )
        product_type = data.get("productType") or "vdbcache"

        for vdb_export_name in vdb_export_names:
            if vdb_export_name in ambiguous_operator_names:
                self.log.warning(
                    "Multiple 'Export VDB' operators named '{}' exist in "
                    "the scene. Rename them to publish this export.".format(
                        vdb_export_name)
                )
                continue
            operator = operators.get(vdb_export_name)
            if operator is None:
                self.log.warning(
                    "No matching 'Export VDB' operator found for "
                    "'{}'. Skipping its product creation.".format(
                        vdb_export_name)
                )
                continue

            product_name = self._get_product_name(
                product_name_template, vdb_export_name)
            self.log.debug(
                "Creating instance for operator: {}".format(vdb_export_name))

            vdb_instance = instance.context.create_instance(product_name)
            vdb_instance.data.update(copy.deepcopy(dict(data)))
            vdb_instance.data.update({
                "name": product_name,
                "label": product_name,
                "family": "vdbcache",
                "families": [
                    "vdbcache",
                    "tyflow_vdb",
                ],
                "productName": product_name,
                "productType": product_type,
                "productBaseType": "vdbcache",
                "creator_identifier": "io.ayon.creators.max.vdb",
                # The product is integrated, the container is not.
                "integrate": True,
                # Operator used to export the VDB files.
                "operator": operator,
            })

    @staticmethod
    def _get_vdb_export_names(container):
        """Get 'Export VDB' operator names selected on the container.

        Args:
            container (rt.MXSWrapperBase): Container instance node.

        Returns:
            list[str]: Names of the selected 'Export VDB' operators.
        """
        modifier = next(iter(container.modifiers), None)
        if modifier is None:
            return []
        if not rt.isProperty(modifier, "AYONTyFlowVDBData"):
            return []
        return list(modifier.AYONTyFlowVDBData.vdb_exports)

    @staticmethod
    def _get_product_name(product_name_template, operator_name):
        """Fill the operator into the product name.

        Product name templates may contain the '{operator}' placeholder
        which is kept unfilled by the creator. If the template does not
        contain it, the operator name is appended to keep product names
        unique.
        """
        operator_name = re.sub(r"\s+", "_", operator_name)
        operator_pattern = r"\{operator\}"
        if re.search(operator_pattern, product_name_template, re.IGNORECASE):
            return re.sub(
                operator_pattern,
                operator_name,
                product_name_template,
                flags=re.IGNORECASE,
            )
        return f"{product_name_template}_{operator_name}"
