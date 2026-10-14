import os
import shutil

import clique
import pyblish.api

from ayon_core.lib import collect_frames
from ayon_core.pipeline import publish


class ExtractLastPublished(publish.Extractor):
    """Extractor copying files from last published to staging directory.

    It works only if instance data includes "last_version_published_files"
    and there are frames to fix.

    The files from last published are based on files which will be
    extended/fixed for specific frames.

    NOTE:
        This plugin is closely taken from ayon-nuke.
        It contains some 3dsMax addon specific logic as various addons may
          have unique methods for managing `staging_dir`, `expectedFiles`
          and `frames`.
    TODO:
        It's preferable to to generalize this plugin for broader use and
          integrate it into ayon-core.
    """

    order = pyblish.api.ExtractorOrder - 0.1
    label = "Extract Last Published"
    targets = ["local"]  # Same target as `CollectFramesFixDef`
    families = ["render.local"]

    def process(self, instance):
        frames_to_fix = instance.data.get("frames_to_fix")
        if not frames_to_fix:
            self.log.debug("Skipping, No frames to fix.")
            return

        if not instance.data.get("integrate", True):
            self.log.debug("Skipping collecting frames to fix data for "
                           "instance because instance is set to not integrate")
            return

        last_published = instance.data.get("last_version_published_files")
        if not last_published:
            self.log.debug("Skipping, No last publish found.")
            return

        last_published_and_frames = collect_frames(last_published)
        if not all(last_published_and_frames.values()):
            self.log.debug("Skipping, No file sequence found in the "
                           "last version published files.")
            return

        expected_filepaths = self.get_expected_files_and_staging_dir(instance)
        if not expected_filepaths:
            self.log.debug(
                "Skipping, no expected files found for the instance."
            )
            return

        # We assume all outputs of this one instance end up in one folder, and
        # hence there being just one 'staging dir'. We will take the first
        # expected file's folder as staging directory.
        staging_dir: str = os.path.dirname(expected_filepaths[0])
        os.makedirs(staging_dir, exist_ok=True)

        expected_and_frames = collect_frames(expected_filepaths)
        frames_and_expected = {v: k for k, v in expected_and_frames.items()}
        frames_to_fix = clique.parse(frames_to_fix, "{ranges}")

        anatomy = instance.context.data["anatomy"]

        # TODO: This currently copies ALL frames from the last version instead
        #  of only those within the frame range we're currently looking to
        #  publish. It should instead, iterate over all expected frames for
        #  current instance, exclude all "to fix" frames and copy the
        #  other existing ones.
        for file_path, frame in last_published_and_frames.items():
            if frame is None:
                continue

            # Last published filepath
            file_path = anatomy.fill_root(file_path)
            if not os.path.exists(file_path):
                continue

            # Expected filepath for this render for that frame
            target_filepath: str = frames_and_expected.get(frame)
            if not target_filepath:
                continue

            # Copy only the frames that we won't render.
            if frame in frames_to_fix:
                continue

            self.log.debug(f"Copying '{file_path}' -> '{target_filepath}'")
            shutil.copy(file_path, target_filepath)

    def get_expected_files_and_staging_dir(self, instance):
        """Get expected file names or frames.

        This method includes 3dsMax specific code. The render instances which
        get integrated keep their files in `representations`, so those are used
        to know where the reused frames have to end up.

        Args:
            instance (pyblish.api.Instance): The instance to publish.

        Returns:
            list[str]: Full paths to the expected filepaths for this publish
                instance.
        """
        expected_filepaths: list[str] = []
        for representation in instance.data.get("representations", []):
            staging_dir = representation.get("stagingDir") or ""
            files = representation.get("files") or []
            if isinstance(files, str):
                files = [files]
            expected_filepaths.extend(
                os.path.join(staging_dir, filename) for filename in files
            )

        return expected_filepaths
