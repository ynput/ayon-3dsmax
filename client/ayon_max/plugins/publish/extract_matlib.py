import os
import pyblish.api
from ayon_core.pipeline import publish
from pymxs import runtime as rt


class ExtractMatlib(publish.Extractor):
    """
    Extract Material Library
    """

    order = pyblish.api.ExtractorOrder - 0.2
    label = "Extract Material Library"
    hosts = ["max"]
    families = ["matlib"]

    settings_category = "max"

    def process(self, instance):
        self.log.debug("Extracting Material Library.")

        stagingdir = self.staging_dir(instance)
        filename = "{name}.mat".format(**instance.data)
        filepath = os.path.join(stagingdir, filename)
        matlib_filepath = instance.data["matlib_filepath"]
        rt.sme.SaveMtlLibAs(matlib_filepath, newPath=filepath)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        self.log.info("Performing Extraction ...")

        representation = {
            "name": "mat",
            "ext": "mat",
            "files": filename,
            "stagingDir": stagingdir,
        }
        instance.data["representations"].append(representation)
        self.log.info(
            "Extracted instance '%s' to: %s" % (instance.name, filepath)
        )
