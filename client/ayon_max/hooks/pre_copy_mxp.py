from ayon_applications import PreLaunchHook, LaunchTypes
from ayon_max.mxp import create_workspace_mxp
from ayon_core.settings import get_project_settings


class PreCopyMxp(PreLaunchHook):
    """Copy workspace.mxp to workdir.

    Hook `GlobalHostDataHook` must be executed before this hook.
    """
    app_groups = {"3dsmax", "adsk_3dsmax"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        project_entity = self.data["project_entity"]
        project_settings = get_project_settings(project_entity.get("name"))
        if not project_settings:
            return
        mxp_workspace = project_settings["max"].get("mxp_workspace")
        # Ensure the hook would not cause possible error
        # when using the old addon.
        if mxp_workspace is None:
            self.log.warning("No mxp workspace setting found in the "
                             "latest Max Addon.")
            return

        workdir = self.launch_context.env.get("AYON_WORKDIR")
        if not workdir:
            self.log.warning("BUG: Workdir is not filled.")
            return

        create_workspace_mxp(workdir, mxp_workspace=mxp_workspace)
