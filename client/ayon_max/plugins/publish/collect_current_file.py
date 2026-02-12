import pyblish.api
from ayon_core.pipeline import registered_host


class CollectCurrentFile(pyblish.api.ContextPlugin):
    """Inject the current working file."""

    order = pyblish.api.CollectorOrder - 0.5
    label = "Max Current File"
    hosts = ['max']

    def process(self, context):
        """Inject the current working file"""
        host = registered_host()
        current_file = host.get_current_workfile()
        if not current_file:
            self.log.error("Scene is not saved.")

        context.data["currentFile"] = current_file
        self.log.debug("Scene path: {}".format(current_file))
