import os
import contextlib
import pyblish.api
from pymxs import runtime as rt

from ayon_max.api.lib import (
    maintained_selection,
    animation_range_without_loop

)

from ayon_core.pipeline import publish


class ExtractTyFlowVDB(publish.Extractor):
    """Extract tycache format with tyFlow operators.
    Notes:
        - TyCache only works for TyFlow Pro Plugin.

    Methods:
        self._extract_tyflow_vdb: sets the necessary
            attributes and export VDB with the export
            particle operator(s)

        self.get_files(): get the files with tyFlow naming convention
            before publishing
    """

    order = pyblish.api.ExtractorOrder - 0.2
    label = "Extract VDB (TyFlow)"
    hosts = ["max"]
    families = ["vdb"]

    def process(self, instance):
        if not instance.data.get("is_tyflow", False):
            self.log.debug(
                "Skipping instances due to non-tyflow VDB workflow used."
            )
            return

        self.log.debug("Extracting VDB...")

        stagingdir = self.staging_dir(instance)
        operator = instance.data["operator"]
        representations = instance.data.setdefault("representations", [])
        start_frame = instance.data["frameStartHandle"]
        end_frame = instance.data["frameEndHandle"]

        product_name = instance.data.get("productName")
        filename = f"{product_name}.vdb"
        path = os.path.join(stagingdir, filename)

        vdb_fnames = self.get_files(
            product_name, start_frame, end_frame)

        with contextlib.ExitStack() as stack:
            stack.enter_context(maintained_selection())
            stack.enter_context(animation_range_without_loop())
            self._extract_tyflow_vdb(
                operator, start_frame, end_frame, path
            )

        representation = {
            "name": "vdb",
            "ext": "vdb",
            "files": (
                vdb_fnames if len(vdb_fnames) > 1
                else vdb_fnames[0]),
            "stagingDir": stagingdir
        }
        representations.append(representation)

    def get_files(self, product_name, start_frame, end_frame):
        """Get file names for tyFlow in VDB format.

        Set the filenames accordingly to the VDB file
        naming extension(.vdb) for the publishing purpose

        Actual File Output from tyFlow in VDB format:
        <InstanceName>_<operator>_<frame>.vdb

        e.g. tyFlowMain_00000.vdb

        Args:
            product_name (str): product name
            start_frame (int): frame start
            end_frame (int): frame end

        Returns:
            filenames(list): list of filenames

        """
        filenames = []
        for frame in range(int(start_frame), int(end_frame) + 1):
            filename = f"{product_name}_{frame:05}.tyc"
            filenames.append(filename)
        return filenames

    def _extract_tyflow_vdb(self, operator, frameStart, frameEnd, filepath):
        """Exports VDB with the necessary export settings

        Args:
            operators (list): List of Export VDB operator
            frameStart (int): Start frame.
            frameEnd (int): End frame.
            filepath (str): Output path of the VDB file.

        """
        export_settings = {
            "timingIntervalStart": int(frameStart),
            "timingIntervalEnd": int(frameEnd),
            "autoExport": True,
            "filename": filepath.replace("\\", "/"),
        }

        for key, value in export_settings.items():
            rt.setProperty(operator, key, value)

        # VDB would be exported when
        # playing the animation in the timeline
        rt.PlayAnimation(immediateReturn=False)
        if not rt.isAnimPlaying():
            self.log.debug(
                "Successfully Extracted all VDB particles."
            )
