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
        # Add requirements to PYTHONPATH
        new_python_paths = [
            os.path.join(MAX_HOST_DIR, "startup")
        ]
        old_python_path = env.get("PYTHONPATH") or ""
        for path in old_python_path.split(os.pathsep):
            if not path:
                continue

            norm_path = os.path.normpath(path)
            if norm_path not in new_python_paths:
                new_python_paths.append(norm_path)

        env["PYTHONPATH"] = os.pathsep.join(new_python_paths)
        env["ADSK_3DSMAX_STARTUPSCRIPTS_ADDON_DIR"] = os.path.join(
            MAX_HOST_DIR, "startup"
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
