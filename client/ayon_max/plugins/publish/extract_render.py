from __future__ import annotations
import contextlib
from ayon_core.pipeline import publish
from ayon_max.api.lib import get_vray_settings

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
            with rendering_output(instance):
                for frame in range(int(rt.rendStart), int(rt.rendEnd) + 1):
                    rt.render(frame=frame, vfb=False)
                    self.log.debug("Local render extraction completed.")
        else:
            self.log.debug(
                "Local render extraction for multi-camera is already "
                "performed during multi-camera scene extraction."
            )


@contextlib.contextmanager
def rendering_output(instance):
    """Make sure to get correct render output path during context

    Args:
        instance (pyblish.api.Instance): The instance to get render output for.

    Returns:
        str: The render output file path.
    """
    original_render_output = get_rendering_output(instance)
    target_render_output = original_render_output.replace(
        instance.data["original_workfile_pattern"],
        instance.data["workfile_name"]
    )
    set_rendering_output(instance, target_render_output)
    try:
        yield

    finally:
        set_rendering_output(instance, original_render_output)



def get_rendering_output(instance):
    """Get the correct render output path during rendering.

    Args:
        instance (pyblish.api.Instance): The instance to get render output for.

    Returns:
        str: The render output file path.
    """
    if instance.data["renderer"].startswith("V_Ray_"):
        vr_settings = get_vray_settings(instance.data["renderer"])
        if vr_settings.output_rawfilename:
            return vr_settings.output_rawfilename

        elif vr_settings.output_splitfilename:
            return vr_settings.output_splitfilename

        else:
            return rt.rendOutputFilename
    else:
        return rt.rendOutputFilename


def set_rendering_output(instance, new_output):
    """Set the correct render output path during rendering.

    Args:
        instance (pyblish.api.Instance): The instance to set render output for.
        new_output (str): The new render output file path.
    """
    if instance.data["renderer"].startswith("V_Ray_"):
        vr_settings = get_vray_settings(instance.data["renderer"])
        if vr_settings.output_rawfilename:
            vr_settings.output_rawfilename = new_output

        elif vr_settings.output_splitfilename:
            vr_settings.output_splitfilename = new_output

        else:
            rt.rendOutputFilename = new_output
    else:
        rt.rendOutputFilename = new_output
