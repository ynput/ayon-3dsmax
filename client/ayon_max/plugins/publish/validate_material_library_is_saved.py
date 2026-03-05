import pyblish.api
from pymxs import runtime as rt

from ayon_core.pipeline import PublishValidationError
from ayon_core.pipeline.publish import RepairAction


class ValidateMaterialLibraryIsSaved(pyblish.api.InstancePlugin):
    """Validates Material Library is saved.

    This validator checks if the material library has modified content
    (Saving, deleting, or renaming Materials, Maps, etc.)
    without saving the material library file.

    """

    order = pyblish.api.ValidatorOrder
    families = ["look"]
    hosts = ["max"]
    label = "Material Library Is Saved"
    actions = [RepairAction]

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            raise PublishValidationError(
                "Material Library must be saved before publishing. "
                f"Invalid types on: {invalid}"
            )

    @classmethod
    def get_invalid(cls, instance):
        """
        Get invalid nodes if the instance is not camera
        """
        invalid = []
        matlib_filepath = instance.data["matlib_filepath"]
        if rt.sme.IsMtlLibModified(matlib_filepath):
            invalid.append(matlib_filepath)
        return invalid

    @classmethod
    def repair(cls, instance):
        """Repair action to save the material library."""
        for invalid_path in cls.get_invalid(instance):
            rt.sme.SaveMtlLib(invalid_path)
