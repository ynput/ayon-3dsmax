import os
import pyblish.api
from ayon_core.pipeline import publish
from pymxs import runtime as rt



class ExtractRenderPreset(publish.Extractor):
    """Extract Render Preset"""

    order = pyblish.api.ExtractorOrder - 0.3
    label = "Extract Render Preset"
    hosts = ["max"]
    families = ["renderpreset"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        filename = f"{instance.name}.rps"
        filepath = os.path.join(staging_dir, filename)
        self.log.debug("Writing Render Preset to '{}'".format(filepath))

        # export render preset for production
        # TODO: we can support to save which presets
        # and which categories later.
        rt.renderpresets.SaveAll(0, filepath)

        representation = {
            "name": "rps",
            "ext": "rps",
            "files": filename,
            "stagingDir": staging_dir,
        }

        self.log.debug(f"{representation}")

        if "representations" not in instance.data:
            instance.data["representations"] = []

        instance.data["representations"].append(representation)
        self.log.info(
            "Extracted instance '%s' to: %s" % (instance.name, filepath)
        )
