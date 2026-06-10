
import pyblish.api
from ayon_max.api.action import SelectInvalidAction
from ayon_core.pipeline.publish import (
    ValidateMeshOrder,
    OptionalPyblishPluginMixin,
    PublishValidationError
)
from pymxs import runtime as rt


class ValidateMeshHasUVs(pyblish.api.InstancePlugin,
                         OptionalPyblishPluginMixin):

    """Validate the current mesh has UVs.

    This validator only checks if the mesh has UVW modifier to ensure
    that UVs are present.

    """

    order = ValidateMeshOrder
    hosts = ['max']
    families = ['model']
    label = 'Validate Mesh Has UVs'
    actions = [SelectInvalidAction]
    optional = True

    settings_category = "max"
    allowed_uv_classes = {
        rt.Uvwmap,
        rt.UVW_Xform,
        rt.UVW_Mapping_Add,
        rt.UVW_Mapping_Clear,
        rt.UVW_Mapping_Paste,
        rt.Unwrap_UVW
    }

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        for member in instance.data["members"]:
            for modifier in member.modifiers:
                if rt.superClassOf(modifier) not in cls.allowed_uv_classes:
                    invalid.append(member)
        return invalid

    def process(self, instance):
        if not self.is_active(instance.data):
            return
        invalid = self.get_invalid(instance)
        if invalid:
            bullet_point_invalid_statement = "\n".join(
                "- {}".format(invalid.name) for invalid
                in invalid
            )
            report = (
                "Model meshes are required to have UVs.\n\n"
                "Meshes detected with invalid or missing UVs:\n"
                f"{bullet_point_invalid_statement}\n"
            )
            raise PublishValidationError(
                report,
                description=(
                "Model meshes are required to have UVs.\n\n"
                "Meshes detected with no texture vertice or missing UVs"
                "Make sure your mesh has UVs and that the UVW modifier is applied to the mesh."),
                title="Non-mesh objects found or mesh has missing UVs")
