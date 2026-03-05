import os
import pyblish.api
from pymxs import runtime as rt

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction


class ValidateNoMaterialLibrary(pyblish.api.InstancePlugin):
    """Validates that no Material Library is present.

    This validator checks if a material library is present
    in the scene to ensure users publishing look instances
    with material libraries. Repair action is provided
    to open the material library if the file exists,
    or clean up the instance if the material library
    file is missing.

    """

    order = pyblish.api.ValidatorOrder
    families = ["look"]
    hosts = ["max"]
    label = "No Material Library"
    actions = [RepairAction]

    def process(self, instance):
        matlib_filepath = instance.data["matlib_filepath"]
        if not os.path.exists(matlib_filepath):
            raise PublishValidationError(
                "Material Library file does not exist. "
                f"Cannot open Material Library at: {matlib_filepath}"
            )
        if not rt.sme.HasMtlLib(matlib_filepath):
            raise PublishValidationError(
                f"Material Library from {instance.name} "
                "is not present before publishing. "
            )


    @classmethod
    def repair(cls, instance):
        """Repair action to open the material library."""
        matlib_filepath = instance.data.get("matlib_filepath")
        if os.path.exists(matlib_filepath):
            rt.sme.OpenMtlLib(matlib_filepath)
        else:
            # Cleaning up the instance if the material library file
            instance_node = rt.GetNodeByName(instance.data["instance_node"])
            if instance_node:
                rt.Delete(instance_node)
