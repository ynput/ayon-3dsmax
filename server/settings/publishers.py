import json
from pydantic import validator

from ayon_server.settings import BaseSettingsModel, SettingsField
from ayon_server.exceptions import BadRequestException


class ValidateAttributesModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="ValidateAttributes")
    attributes: str = SettingsField(
        "{}", title="Attributes", widget="textarea")

    @validator("attributes")
    def validate_json(cls, value):
        if not value.strip():
            return "{}"
        try:
            converted_value = json.loads(value)
            success = isinstance(converted_value, dict)
        except json.JSONDecodeError:
            success = False

        if not success:
            raise BadRequestException(
                "The attibutes can't be parsed as json object"
            )
        return value


class ValidateCameraAttributesModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")
    fov: float = SettingsField(0.0, title="Focal Length")
    nearrange: float = SettingsField(0.0, title="Near Range")
    farrange: float = SettingsField(0.0, title="Far Range")
    nearclip: float = SettingsField(0.0, title="Near Clip")
    farclip: float = SettingsField(0.0, title="Far Clip")


class FamilyMappingItemModel(BaseSettingsModel):
    families: list[str] = SettingsField(
        default_factory=list,
        title="Families"
    )
    plugins: list[str] = SettingsField(
        default_factory=list,
        title="Plugins"
    )


class ValidateModelNameModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")
    regex: str = SettingsField(
        "(.*)_(?P<subset>.*)_(GEO)",
        title="Validation regex",
        description=(
            "Regex for validating model name. You can use named "
            " capturing groups:(?P<asset>.*) for Asset name"
        )
    )


class ValidateLoadedPluginModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    family_plugins_mapping: list[FamilyMappingItemModel] = SettingsField(
        default_factory=list,
        title="Family Plugins Mapping"
    )


class BasicValidateModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    optional: bool = SettingsField(title="Optional")
    active: bool = SettingsField(title="Active")


class PublishersModel(BaseSettingsModel):
    ValidateInstanceInContext: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Instance In Context",
        section="Validators"
    )
    ValidateFrameRange: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Frame Range"
    )
    ValidateTyCacheFrameRange: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Frame Range (TyCache)"
    )
    ValidateTyVDBFrameRange: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Frame Range (TyFlow VDB)"
    )
    ValidateAttributes: ValidateAttributesModel = SettingsField(
        default_factory=ValidateAttributesModel,
        title="Validate Attributes"
    )
    ValidateCameraAttributes: ValidateCameraAttributesModel = SettingsField(
        default_factory=ValidateCameraAttributesModel,
        title="Validate Camera Attributes",
        description=(
            "If the value of the camera attributes set to 0, "
            "the system automatically skips checking it"
        )
    )
    ValidateNoAnimation: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate No Animation"
    )
    ValidateLoadedPlugin: ValidateLoadedPluginModel = SettingsField(
        default_factory=ValidateLoadedPluginModel,
        title="Validate Loaded Plugin"
    )
    ValidateMeshHasUVs: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Mesh Has UVs"
    )
    ValidateModelName: ValidateModelNameModel = SettingsField(
        default_factory=ValidateModelNameModel,
        title="Validate Model Name"
    )
    ValidateRenderPasses: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Validate Render Passes"
    )
    ExtractModelObj: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Extract OBJ",
        section="Extractors"
    )
    ExtractModelFbx: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Extract FBX"
    )
    ExtractModelUSD: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Extract Geometry (USD)"
    )
    ExtractModel: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Extract Geometry (Alembic)"
    )
    ExtractMaxSceneRaw: BasicValidateModel = SettingsField(
        default_factory=BasicValidateModel,
        title="Extract Max Scene (Raw)"
    )


DEFAULT_PUBLISH_SETTINGS = {
    "ValidateInstanceInContext": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateFrameRange": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ValidateTyCacheFrameRange": {
        "enabled": False,
        "optional": True,
        "active": True
    },
    "ValidateTyVDBFrameRange": {
        "enabled": False,
        "optional": True,
        "active": True
    },
    "ValidateAttributes": {
        "enabled": False,
        "attributes": "{}"
    },
    "ValidateCameraAttributes": {
        "enabled": True,
        "optional": True,
        "active": False,
        "fov": 45.0,
        "nearrange": 0.0,
        "farrange": 1000.0,
        "nearclip": 1.0,
        "farclip": 1000.0
    },
    "ValidateModelName": {
        "enabled": True,
        "optional": True,
        "active": False,
        "regex": "(.*)_(?P<subset>.*)_(GEO)"
    },
    "ValidateLoadedPlugin": {
        "enabled": False,
        "optional": True,
        "family_plugins_mapping": []
    },
    "ValidateMeshHasUVs": {
        "enabled": True,
        "optional": True,
        "active": False
    },
    "ValidateNoAnimation": {
        "enabled": True,
        "optional": True,
        "active": False,
    },
    "ValidateRenderPasses": {
        "enabled": True,
        "optional": False,
        "active": True
    },
    "ExtractModelObj": {
        "enabled": True,
        "optional": True,
        "active": False
    },
    "ExtractModelFbx": {
        "enabled": True,
        "optional": True,
        "active": False
    },
    "ExtractModelUSD": {
        "enabled": True,
        "optional": True,
        "active": False
    },
    "ExtractModel": {
        "enabled": True,
        "optional": True,
        "active": True
    },
    "ExtractMaxSceneRaw": {
        "enabled": True,
        "optional": True,
        "active": True
    }
}
