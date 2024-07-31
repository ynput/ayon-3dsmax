from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_max.mxp import create_workspace_mxp


class PreCopyMxp(PreLaunchHook):
    """Copy workspace.mxp to workdir.

    Hook `GlobalHostDataHook` must be executed before this hook.
    """
    app_groups = {"3dsmax", "adsk_3dsmax"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        max_setting = self.data["project_settings"]["max"]
        mxp_workspace = max_setting.get("mxp_workspace")
        # Ensure the hook would not cause possible error
        # when using the old addon.
        if mxp_workspace is None:
            self.log.warning("No mxp workspace setting found in the "
                             "latest Max Addon.")
            return
        enabled_project_creation = mxp_workspace.get("enabled_project_creation")
        if not enabled_project_creation:
            self.log.debug("3dsmax project creation is not enabled. "
                           "Skipping creating workspace.mxp to workdir.")
            return
        workdir = self.launch_context.env.get("AYON_WORKDIR")
        if not workdir:
            self.log.warning("BUG: Workdir is not filled.")
            return

        create_workspace_mxp(workdir, mxp_workspace=mxp_workspace)
