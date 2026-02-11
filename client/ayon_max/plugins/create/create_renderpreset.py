"""Creator plugin for creating render preset."""
from ayon_max.api.plugin import MaxCreator


class CreateRenderPreset(MaxCreator):
    identifier = "io.ayon.creators.max.renderpreset"
    label = "Render Preset"
    product_base_type = "renderpreset"
    product_type = product_base_type
    icon = "tablet"

    def get_pre_create_attr_defs(self):
        return []
