# -*- coding: utf-8 -*-
"""Extractor for VDB files written by TyFlow's 'Export VDB' operator."""
import contextlib
import os
import re

import pyblish.api
from pymxs import runtime as rt

from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import PublishError
from ayon_max.api.lib import (
    animation_range_without_loop,
    maintained_selection,
    maintained_tyflow_vdb_export,
)


class ExtractTyFlowVDB(publish.Extractor):
    """Extract VDB files with a TyFlow 'Export VDB' operator.

    TyFlow writes the VDB files while the animation is played. The
    operator is switched into 'auto export' mode only for the duration of
    the extraction, and the exported files are validated against the
    instance frame range before a representation is created.
    """

    order = pyblish.api.ExtractorOrder - 0.2
    label = "Extract VDB (TyFlow)"
    hosts = ["max"]
    families = ["tyflow_vdb"]

    def process(self, instance):
        self.log.debug("Extracting VDB...")

        stagingdir = self.staging_dir(instance)
        operator = instance.data["operator"]
        representations = instance.data.setdefault("representations", [])
        start_frame = int(instance.data["frameStartHandle"])
        end_frame = int(instance.data["frameEndHandle"])

        product_name = instance.data["productName"]
        filepath = os.path.join(stagingdir, f"{product_name}.vdb")

        with contextlib.ExitStack() as stack:
            stack.enter_context(maintained_selection())
            stack.enter_context(
                animation_range_without_loop(start_frame, end_frame)
            )
            stack.enter_context(
                maintained_tyflow_vdb_export(operator, filepath)
            )
            # VDB files are written while the animation is played.
            rt.PlayAnimation(immediateReturn=False)

        files = self._get_exported_files(
            stagingdir, start_frame, end_frame)

        representation = {
            "name": "vdb",
            "ext": "vdb",
            "files": files if len(files) > 1 else files[0],
            "stagingDir": stagingdir,
        }
        representations.append(representation)
        self.log.debug(
            f"Extracted {len(files)} VDB file(s) to: {stagingdir}")

    def _get_exported_files(self, stagingdir, start_frame, end_frame):
        """Get the exported VDB files and validate the frame range.

        Args:
            stagingdir (str): Directory where the VDB files were written.
            start_frame (int): Expected first frame.
            end_frame (int): Expected last frame.

        Returns:
            list[str]: Exported VDB filenames sorted by frame.
        """
        exported_files = []
        for filename in os.listdir(stagingdir):
            if not filename.lower().endswith(".vdb"):
                continue
            exported_files.append(
                (self._get_frame_from_filename(filename), filename)
            )
        exported_files.sort(key=lambda item: (item[0] is None, item[0] or 0))

        if not exported_files:
            raise PublishError(
                "No VDB files were exported to '{}'. Make sure the TyFlow "
                "flow is simulated and that an 'Export VDB' operator is "
                "added to the instance.".format(stagingdir)
            )

        filenames = [filename for _, filename in exported_files]
        expected_frames = set(range(start_frame, end_frame + 1))
        exported_frames = {
            frame for frame, _ in exported_files if frame is not None
        }
        missing_frames = expected_frames - exported_frames
        if missing_frames:
            raise PublishError(
                "Exported VDB files do not match the expected frame range "
                "({}-{}). Missing frames: {}. Exported files: {}".format(
                    start_frame,
                    end_frame,
                    ", ".join(
                        str(frame) for frame in sorted(missing_frames)),
                    ", ".join(filenames),
                )
            )
        return filenames

    @staticmethod
    def _get_frame_from_filename(filename):
        """Get the frame number from a VDB filename, if there is any.

        Args:
            filename (str): Name of the exported VDB file.

        Returns:
            int | None: Frame number parsed from the filename.
        """
        match = re.search(r"(\d+)(?!.*\d)", os.path.splitext(filename)[0])
        if match is None:
            return None
        return int(match.group(1))
