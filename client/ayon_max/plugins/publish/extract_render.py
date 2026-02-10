from __future__ import annotations
from ayon_core.pipeline import publish


try:
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
            for frame in range(int(rt.rendStart), int(rt.rendEnd) + 1):
                rt.render(frame=frame, vfb=False, camera=camera_node)
                self.log.debug("Local render extraction completed.")
        else:
            self.log.debug(
                "Local render extraction for multi-camera is already "
                "performed during multi-camera scene extraction."
            )
