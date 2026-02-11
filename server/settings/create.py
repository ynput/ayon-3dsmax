from ayon_server.settings import BaseSettingsModel, SettingsField


class ProductTypeItemModel(BaseSettingsModel):
    _layout = "compact"
    product_type: str = SettingsField(
        title="Product type",
        description="Product type name",
    )
    label: str = SettingsField(
        title="Label",
        description="Label to display in UI for the product type",
    )


class CreatePluginModel(BaseSettingsModel):
    product_type_items: list[ProductTypeItemModel] = SettingsField(
        default_factory=list,
        title="Product type items",
        description=(
            "Optional list of product types that this plugin can create."
        )
    )


class CreateModel(BaseSettingsModel):
    CreateCamera: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Camera"
    )
    CreateMaxScene: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Max Scene"
    )
    CreateModel: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Model"
    )
    CreatePointCache: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Point Cache"
    )
    CreatePointCloud: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Point Cloud"
    )
    CreateRedshiftProxy: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Redshift Proxy"
    )
    CreateRender: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Render"
    )
    CreateRenderPreset: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="Render Preset"
    )
    CreateTyFlow: CreatePluginModel = SettingsField(
        default_factory=CreatePluginModel,
        title="TyFlow"
    )


