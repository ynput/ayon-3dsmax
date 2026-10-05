from typing import Optional

import pyblish.api
from ayon_core.pipeline import (
    OptionalPyblishPluginMixin
)
from ayon_core.pipeline.publish import (
    RepairAction,
    PublishValidationError
)
from ayon_max.api.lib import (
    reset_scene_resolution,
    imprint
)


class ValidateResolutionSetting(pyblish.api.InstancePlugin,
                                OptionalPyblishPluginMixin):
    """Validate the resolution setting aligned with DB"""

    order = pyblish.api.ValidatorOrder - 0.01
    families = ["maxrender"]
    hosts = ["max"]
    label = "Validate Resolution Setting"
    optional = True
    actions = [RepairAction]

    def process(self, instance) -> None:
        if (
            "render.local" in instance.data["families"] or
            "render.local_no_render" in instance.data["families"]
        ):
            self.log.debug(
                "Skipping Validate Frame Range for "
                "local render instance as it is already validated."
            )
            return
        if not self.is_active(instance.data):
            return

        context_resolution = self.get_context_resolution(instance)
        if context_resolution is None:
            self.log.debug(
                "Skipping resolution validation for instance '%s': no "
                "task or folder entity resolution found.", instance.name
            )
            return
        width, height = context_resolution
        current_width, current_height = (
            self.get_current_resolution(instance)
        )

        if current_width != width:
            raise PublishValidationError("Width in Resolution Setting "
                                         "not matching resolution set "
                                         "on asset or shot.")

        if current_height != height:
            raise PublishValidationError("Height in Resolution Setting "
                                         "not matching resolution set "
                                         "on asset or shot.")
        if (current_width, current_height) != (width, height):
            raise PublishValidationError(
                "Resolution is incorrect.\n\n"
                f"Current resolution: {current_width}x{current_height}\n"
                f"Expected resolution: {width}x{height}\n\n"
                "The expected resolution is set on the task context. "
                "You can use the repair action to set it.",
                title="Incorrect Resolution",
            )

    def get_current_resolution(self, instance) -> tuple[int, int]:
        return instance.data["resolutionWidth"], instance.data["resolutionHeight"]

    @classmethod
    def get_context_resolution(
        cls,
        instance: pyblish.api.Instance
    ) -> Optional[tuple[int, int]]:
        """Get the resolution set on the task (or folder if no task).

        Args:
            instance (pyblish.api.Instance): The instance to get the
                task or folder resolution from.

        Returns:
            Optional[tuple[int, int]]: The resolution set on the entity
                (width, height), or None when the task/folder entity does
                not define a resolution.
        """
        entity = (
            instance.data.get("taskEntity")
            or instance.data.get("folderEntity")
        )
        if entity:
            attributes = entity["attrib"]
            width = attributes.get("resolutionWidth")
            height = attributes.get("resolutionHeight")
            if width is not None and height is not None:
                return int(width), int(height)

        return None

    @classmethod
    def repair(cls, instance) -> None:
        entity = (
            instance.data.get("taskEntity")
            or instance.data.get("folderEntity")
        )
        reset_scene_resolution(entity)


class ValidateReviewResolutionSetting(ValidateResolutionSetting):
    families = ["review"]
    label = "Validate Review Resolution Setting"
    optional = True
    actions = [RepairAction]

    @classmethod
    def repair(cls, instance) -> None:
        context_width, context_height = cls.get_context_resolution(instance)
        creator_attrs = instance.data["creator_attributes"]
        creator_attrs["review_width"] = context_width
        creator_attrs["review_height"] = context_height
        creator_attrs_data = {
            "creator_attributes": creator_attrs
        }
        # update the width and height of review
        # data in creator_attributes
        imprint(instance.data["instance_node"], creator_attrs_data)
