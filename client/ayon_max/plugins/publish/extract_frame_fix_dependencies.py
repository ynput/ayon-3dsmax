"""Prepare the reused frames a farm frame fix needs before submission.

A farm publish job lists every frame of the version in its representations.
When the Deadline publish job waits for the rendered files (the ayon-deadline
setting `Add rendered files as Dependencies`), it only starts once all of them
exist. A frame fix renders only part of the frames and copies the rest from
the previous version while the publish job runs, so the copied frames have to
exist before the publish job is submitted, otherwise it waits forever.

`CollectFramesFixDefMax` collects these files, this plugin copies them right
before the Deadline submission happens.
"""
import os
import shutil

import pyblish.api



def copy_reused_files(copies, log=None):
    """Copy the reused frames into the staging directory of the publish job.

    Args:
        copies (list[tuple[str, str]]): Source and target file paths.
        log (Optional[logging.Logger]): Logger for the skipped files.

    Returns:
        tuple[int, int, int]: Number of copied, already existing and missing
            files.

    """
    copied = skipped = missing = 0
    for source, target in copies:
        if os.path.exists(target):
            skipped += 1
            continue
        if not os.path.exists(source):
            missing += 1
            if log is not None:
                log.warning(
                    "Cannot prepare the reused frame, its file is missing: %s",
                    source)
            continue
        target_dir = os.path.dirname(target)
        if target_dir:
            os.makedirs(target_dir, exist_ok=True)
        shutil.copy2(source, target)
        copied += 1
    return copied, skipped, missing


class ExtractFrameFixDependencies(pyblish.api.InstancePlugin):
    """Copy the reused frames before the farm publish job is submitted."""

    order = pyblish.api.ExtractorOrder + 0.05
    label = "Extract Frame Fix Dependencies"
    families = ["maxrender"]
    hosts = ["max"]
    targets = ["local"]

    def process(self, instance):
        copies = instance.data.get("frame_fix_reused_files") or []
        if not copies:
            return

        if not self.is_rendered_file_dependencies_enabled(instance):
            self.log.debug(
                "The Deadline publish job does not wait for rendered files, "
                "the reused frames are copied by the publish job itself.")
            return

        copied, skipped, missing = copy_reused_files(copies, self.log)
        self.log.info(
            "Prepared the reused frames for the Deadline publish job: "
            "%s copied, %s already present, %s missing.",
            copied, skipped, missing)

    def is_rendered_file_dependencies_enabled(self, instance) -> bool:
        """Check whether the Deadline publish job waits for rendered files.

        Returns:
            bool: True when the publish job waits for the rendered files.

        """
        deadline_settings = instance.context.data["project_settings"].get("deadline", {})
        submit_publish_job = deadline_settings.get("publish", {}).get(
            "ProcessSubmittedJobOnFarm", {}
        )
        return submit_publish_job.get("add_rendered_dependencies", False)
