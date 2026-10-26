from __future__ import annotations

import os
import shutil

import clique
import pyblish.api
import ayon_api

from ayon_core.lib import collect_frames
from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import PublishError


def _iter_representation_files(instance):
    """Iterate the staging directory and file name of every representation.

    Args:
        instance (pyblish.api.Instance): The instance to publish.

    Yields:
        tuple[str, str]: Staging directory and file name.

    """
    anatomy = instance.context.data["anatomy"]
    for representation in instance.data.get("representations") or []:
        staging_dir = representation.get("stagingDir") or ""
        # The staging directory of an instance which is published on the farm
        # is a rootless path.
        if staging_dir.startswith("{"):
            staging_dir = anatomy.fill_root(staging_dir)
        files = representation.get("files") or []
        if isinstance(files, str):
            files = [files]
        for file_name in files:
            yield staging_dir, file_name


class ExtractLastPublished(publish.Extractor):
    """Extractor copying files from last published to staging directory.

    It works only if there are frames to fix. The files of the previous
    version are either collected by `CollectFramesFixDefMax` into
    "last_version_published_files", or resolved from the product of the
    instance, which is the case for a publish on the farm.

    The files from last published are based on files which will be
    extended/fixed for specific frames.

    NOTE:
        This plugin is closely taken from ayon-nuke.
        It contains some 3dsMax addon specific logic as various addons may
          have unique methods for managing `staging_dir`, `expectedFiles`
          and `frames`.
    TODO:
        It's preferable to generalize this plugin for broader use and
          integrate it into ayon-core.
    """

    order = pyblish.api.ExtractorOrder - 0.1
    label = "Extract Last Published"
    # `render.local` are the instances spawned for a local render, `render` is
    # the family of the instances which are published on the farm.
    families = ["render.local", "render"]

    def process(self, instance):
        # `frames_to_render` lists every frame which is rendered and is
        # collected by `CollectFramesFixDefMax`, `frames_to_fix` is only used
        # as a fallback.
        frames_to_render = instance.data.get("frames_to_render")
        frames_to_fix = instance.data.get("frames_to_fix")
        if not frames_to_render and not frames_to_fix:
            self.log.debug("Skipping, No frames to fix or render found.")
            return

        if not instance.data.get("integrate", True):
            self.log.debug("Skipping, instance is not integrated.")
            return

        expected_filepaths = self.get_expected_files_and_staging_dir(instance)
        if not expected_filepaths:
            self.log.debug(
                "Skipping, no expected files found for the instance."
            )
            return

        if frames_to_render:
            rendered_frames = {int(frame) for frame in frames_to_render}
        else:
            rendered_frames = set(
                clique.parse(frames_to_fix, "{ranges}").indexes)

        # Every expected frame which is not rendered has to be copied, the
        # rendered frames are written by the render itself.
        frames_and_expected = {
            frame: filepath
            for filepath, frame in collect_frames(expected_filepaths).items()
            if frame is not None and int(frame) not in rendered_frames
        }
        if not frames_and_expected:
            self.log.debug(
                "Skipping, all expected frames of the instance are rendered."
            )
            return

        # The local render instances get the files of the previous version
        # from `CollectFramesFixDefMax`. The instances which are published on
        # the farm are created during the submission, so they resolve the
        # previous version of their own product.
        last_published = (
            instance.data.get("last_version_published_files")
            or self._get_last_published_files(instance)
        )
        last_published_and_frames = (
            collect_frames(last_published) if last_published else {}
        )
        last_published_and_frames = {
            path: frame for path, frame in last_published_and_frames.items()
            if frame is not None
        }
        if not last_published_and_frames:
            raise PublishError(
                "No previous version found for the frames which are not "
                "re-rendered."
            )

        # All outputs of one instance end up in one folder, so the folder of
        # the first expected file is used as the staging directory.
        staging_dir: str = os.path.dirname(expected_filepaths[0])
        os.makedirs(staging_dir, exist_ok=True)

        anatomy = instance.context.data["anatomy"]

        for file_path, frame in last_published_and_frames.items():
            target_filepath = frames_and_expected.get(frame)
            if not target_filepath:
                # the frame is not part of this render
                continue

            file_path = anatomy.fill_root(file_path)
            if not os.path.exists(file_path):
                continue

            self.log.debug(f"Copying '{file_path}' -> '{target_filepath}'")
            shutil.copy(file_path, target_filepath)

        # Frames which are neither rendered nor available in the previous
        # version would be silently missing in the published version.
        missing_files = sorted(
            filepath for filepath in frames_and_expected.values()
            if not os.path.exists(filepath)
        )
        if missing_files:
            raise PublishError(
                "Missing files for the frames which are not re-rendered: "
                + ", ".join(missing_files)
            )

    def get_expected_files_and_staging_dir(self, instance):
        """Get the expected filepaths of the instance.

        The render instances which get integrated keep their files in
        `representations`, so those are used to know where the reused frames
        have to end up.

        Args:
            instance (pyblish.api.Instance): The instance to publish.

        Returns:
            list[str]: Full paths to the expected filepaths for this publish
                instance.

        """
        return [
            os.path.join(staging_dir, file_name)
            for staging_dir, file_name in _iter_representation_files(instance)
        ]

    def _get_last_published_files(self, instance):
        """Get the published files of the previous version of the product.

        Args:
            instance (pyblish.api.Instance): The instance to publish.

        Returns:
            list[str]: Published files of the last version of the product.

        """
        product_name = instance.data.get("productName")
        if not product_name:
            self.log.debug(
                "No product name collected, cannot resolve the previous "
                "version of the product."
            )
            return []

        project_name = instance.context.data["projectName"]
        folder_entity = instance.data["folderEntity"]

        product_entity = ayon_api.get_product_by_name(
            project_name, product_name, folder_id=folder_entity["id"])
        if not product_entity:
            self.log.debug(
                "No existing product found for '%s'.", product_name)
            return []

        version_entity = ayon_api.get_last_version_by_product_id(
            project_name, product_id=product_entity["id"])
        if not version_entity:
            return []

        published_files: list[str] = []
        for representation in ayon_api.get_representations(
                project_name, version_ids={version_entity["id"]}):
            for file_info in representation.get("files") or []:
                published_files.append(file_info["path"])

        # The output format may have changed since the previous version, only
        # files of the current representations can be reused.
        current_extensions = set()
        for _, file_name in _iter_representation_files(instance):
            extension = os.path.splitext(file_name)[1].lower()
            if extension:
                current_extensions.add(extension)
        if not current_extensions:
            return published_files

        return [
            file_path for file_path in published_files
            if os.path.splitext(file_path)[1].lower() in current_extensions
        ]
