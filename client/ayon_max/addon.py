# -*- coding: utf-8 -*-
import os
from ayon_core.addon import AYONAddon, IHostAddon

from .version import __version__

MAX_HOST_DIR = os.path.dirname(os.path.abspath(__file__))


class MaxAddon(AYONAddon, IHostAddon):
    name = "max"
    version = __version__
    host_name = "max"

    def add_implementation_envs(self, env, _app):
        # Add requirements to ADSK_3DSMAX_STARTUPSCRIPTS_ADDON_DIR
        new_addon_paths = [
            os.path.join(MAX_HOST_DIR, "startup")
        ]
        old_addon_paths = env.get("ADSK_3DSMAX_STARTUPSCRIPTS_ADDON_DIR") or ""
        for path in old_addon_paths.split(os.pathsep):
            if not path:
                continue

            norm_path = os.path.normpath(path)
            if norm_path not in new_addon_paths:
                new_addon_paths.append(norm_path)

        # 3dsmax docs state this is a semi-colon separated list. It does not
        # state it uses the path separator, hence we use ; directly instead
        # of os.pathsep
        env["ADSK_3DSMAX_STARTUPSCRIPTS_ADDON_DIR"] = ";".join(
            new_addon_paths
        )
        # Remove auto screen scale factor for Qt
        # - let 3dsmax decide it's value
        env.pop("QT_AUTO_SCREEN_SCALE_FACTOR", None)

    def get_workfile_extensions(self):
        return [".max"]

    def get_launch_hook_paths(self, app):
        if app.host_name != self.host_name:
            return []
        return [
            os.path.join(MAX_HOST_DIR, "hooks")
        ]
