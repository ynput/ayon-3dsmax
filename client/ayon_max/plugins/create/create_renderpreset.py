"""Creator plugin for creating render preset."""
from ayon_max.api import plugin


class CreateRenderPreset(plugin.MaxCreator):
    identifier = "io.ayon.creators.max.renderpreset"
    label = "Render Preset"
    product_type = "renderpreset"
    product_base_type = "renderpreset"
    icon = "tablet"

    settings_category = "max"

    def get_pre_create_attr_defs(self):
        return []
