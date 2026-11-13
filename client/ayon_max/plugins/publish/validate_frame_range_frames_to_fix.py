import clique

import pyblish.api
from ayon_core.pipeline import PublishValidationError


class ValidateFrameRangeFramesToFix(pyblish.api.InstancePlugin):
    """Validate the frames to fix against the instance frame range.

    The instance may only report frames to fix which are inside the frame range
    the instance renders. Frames which are not rendered cannot be fixed, and the
    frames which are not being fixed are copied from the previous published
    version.
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range Frames to Fix"
    # The frames to fix and the frame range belong to the render instance which
    # triggers the render. The render instances spawned from it are the ones
    # which get integrated and they are not validated here.
    families = ["maxrender"]

    def process(self, instance):
        frames_to_fix: str = instance.data.get("frames_to_fix", "")
        if not frames_to_fix:
            self.log.debug("Skipping Validation, no frames to fix.")
            return

        # Get the frame range from 'frames to fix'
        try:
            collection = clique.parse(frames_to_fix, "{ranges}")
        except ValueError:
            # Invalid frame pattern entered
            raise PublishValidationError(
                f"Invalid frames to fix pattern: '{frames_to_fix}'",
                description=(
                    "The frames to fix pattern specified is invalid. It must "
                    "be of the form `5,10-15`.\n\n"
                    "The pattern must be a comma-separated list of frames or "
                    "frame ranges. A frame is a whole number, like `5`, and a "
                    "frame range is two whole numbers separated by a hyphen, "
                    "like `5-10` indicating the frames `5,6,7,8,9,10`."
                )
            )

        # `collection.indexes` are integers while the collection items are zero
        # padded strings; both compared values have to be integers.
        fix_frames: "set[int]" = set(collection.indexes)
        if not fix_frames:
            raise PublishValidationError(
                f"Frames to fix '{frames_to_fix}' does not contain any frame.",
                description=(
                    "## No frames to fix\n"
                    "The frames to fix value does not contain any frame. Use a "
                    "value like `5,10-15` and make sure a range's start frame is "
                    "lower than its end frame."
                ),
            )

        expected_frames = set(instance.data.get("expectedFrameRange") or [])
        if not expected_frames:
            self.log.debug("No expected frame range collected, skipping.")
            return
        missing_frames = sorted(fix_frames - expected_frames)
        if missing_frames:
            raise PublishValidationError(
                f"Frames to fix {missing_frames} are not rendered by this "
                "instance.",
                description=(
                    "## Frames to fix outside the instance frame range\n"
                    f"The instance renders {sorted(expected_frames)} but these "
                    f"frames to fix would not be rendered: {missing_frames}."
                ),
            )
