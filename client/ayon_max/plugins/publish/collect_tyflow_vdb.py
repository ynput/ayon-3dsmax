import pyblish.api
import re
import copy
from ayon_core.lib import BoolDef
from ayon_core.pipeline.publish import AYONPyblishPluginMixin
from ayon_max.api.lib import get_tyflow_export_operators
from pymxs import runtime as rt


class CollectTyFlowVDBData(pyblish.api.InstancePlugin,
                           AYONPyblishPluginMixin):
    """Collect TyFlow Attributes for VDB Export"""

    order = pyblish.api.CollectorOrder + 0.005
    label = "Collect TyFlow VDB attribute Data"
    hosts = ['max']
    families = ["tyflow_vdb"]
    validate_tyvdb_frame_range = True

    @classmethod
    def apply_settings(cls, project_settings):

        settings = (
            project_settings["max"]["publish"]["ValidateTyVDBFrameRange"]
        )
        cls.validate_tyvdb_frame_range = settings["active"]

    def process(self, instance):
        context = instance.context
        container_name = instance.data["instance_node"]
        container = rt.GetNodeByName(container_name)
        vdb_product_names = [
            name for name
            in container.modifiers[0].AYONTyFlowVDBData.vdb_exports
        ]
        attr_values = self.get_attr_values_from_data(instance.data)
        for vdb_product_name in vdb_product_names:
            self.log.debug(f"Creating instance for operator:{vdb_product_name}")
            tyc_instance = context.create_instance(vdb_product_name)
            tyc_instance[:] = instance[:]
            tyc_instance.data.update(copy.deepcopy(dict(instance.data)))
            # Replace all runs of whitespace with underscore
            prod_name = re.sub(r"\s+", "_", vdb_product_name)
            operator = next((
                    node for node in 
                    get_tyflow_export_operators(operator_type="exportVDB")
                    if node.name == vdb_product_name),
                    None
            )
            tyc_instance.data.update({
                "name": f"{prod_name}",
                "label": f"{prod_name}",
                "family": "vdbcache",
                "productName": f"{prod_name}",
                # get the name of operator for the export
                "operator": operator,
                "productType": "vdbcache"
            })
            instance.append(tyc_instance)
            if attr_values.get("has_frame_range_validator",
                               self.validate_tyvdb_frame_range):

                instance.data["families"].append("vdb_frame_validation")

        # Skip integrating original instance.
        instance.data["integrate"] = False

    @classmethod
    def get_attribute_defs(cls):
        return [
            BoolDef("has_frame_range_validator",
                    label="Validate TyCache Frame Range",
                    default=cls.validate_tyvdb_frame_range),
        ]
