from __future__ import annotations

import os
from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import KnownPublishError


try:
    import pymxs
    from pymxs import runtime as rt

except ImportError:
    rt = None


class ExtractLocalRender(publish.Extractor):
    """Extract local render for 3dsmax"""

    label = "Extract Local Render"
    families = ["maxrender"]

    def process(self, instance):
        # Skip if explicitly marked for farm
        if instance.data.get("farm"):
            self.log.debug("Instance marked for farm, skipping local render.")
            return

        if instance.data.get("creator_attributes", {}).get(
            "render_target"
        ) != "local":
            self.log.debug(
                "Instance render target is not local, skipping local render."
            )
            return
        if not instance.data.get("multiCamera"):
            camera = next(iter(instance.data.get("cameras", [])), None)
            camera_node = (
                rt.getNodeByName(camera)
                if camera else rt.viewport.GetCamera()
            )
            kwargs = {
                "camera_node": camera_node,
                "cancelled": pymxs.byref(None),
                "vfb": False,
            }
            for frame in instance.data["expectedFrameRange"]:
                if instance.data["renderer"].startswith("Arnold"):
                    filename, ext = os.path.splitext(rt.rendOutputFilename)
                    new_output = f"{filename}{frame:04d}{ext}"
                    kwargs["outputFile"] = new_output
                _, cancelled = rt.render(
                    frame=frame,
                    **kwargs
                )
                if cancelled:
                    raise KnownPublishError(f"Render cancelled at frame {frame}.")
            self.log.debug("Local render extraction completed.")
        else:
            self.log.debug(
                "Local render extraction for multi-camera is already "
                "performed during multi-camera scene extraction."
            )
