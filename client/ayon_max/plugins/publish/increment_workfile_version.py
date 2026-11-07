import os

import pyblish.api
from pymxs import runtime as rt

from ayon_core.lib import version_up


class IncrementWorkfileVersion(pyblish.api.ContextPlugin):
    """Increment current workfile version."""

    order = pyblish.api.IntegratorOrder + 0.9
    label = "Increment Workfile Version"
    hosts = ["max"]
    families = ["maxrender", "workfile"]

    def process(self, context):
        path = context.data["currentFile"]
        try:
            from ayon_core.pipeline.workfile import save_next_version
            from ayon_core.host.interfaces import SaveWorkfileOptionalData

            current_filename = os.path.basename(path)
            save_next_version(
                description=(
                    f"Incremented by publishing from {current_filename}"
                ),
                # Optimize the save by reducing needed queries for context
                prepared_data=SaveWorkfileOptionalData(
                    project_entity=context.data["projectEntity"],
                    project_settings=context.data["project_settings"],
                    anatomy=context.data["anatomy"],
                )
            )
        except ImportError:
            # Backwards compatibility before ayon-core 1.5.0
            filepath = version_up(path)

            rt.saveMaxFile(filepath)

        self.log.info("Incrementing file version")
