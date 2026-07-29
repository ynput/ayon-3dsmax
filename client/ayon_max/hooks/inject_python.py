# -*- coding: utf-8 -*-
"""Pre-launch hook to inject python environment."""
import os
from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_max import MAX_HOST_DIR


class InjectPythonPath(PreLaunchHook):
    """Inject AYON environment to 3dsmax.

    Note that this works in combination with 3dsmax startup script that
    is translating it back to PYTHONPATH for cases when 3dsmax drops PYTHONPATH
    environment.

    Hook `GlobalHostDataHook` must be executed before this hook.
    """
    app_groups = {"3dsmax", "adsk_3dsmax"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        pythonpath_value = self.launch_context.env.get("PYTHONPATH")
        if pythonpath_value is None:
            pythonpath_value = os.environ.get("PYTHONPATH", "")

        paths = [path for path in pythonpath_value.split(os.pathsep) if path]
        addon_client_path = os.path.join(MAX_HOST_DIR, "client")
        if addon_client_path not in paths:
            paths.append(addon_client_path)

        self.launch_context.env["MAX_PYTHONPATH"] = os.pathsep.join(paths)
