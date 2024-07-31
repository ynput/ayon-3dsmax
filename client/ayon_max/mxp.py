import os
from ayon_core.lib import Logger


def create_workspace_mxp(workdir, mxp_workspace=None):
    dst_filepath = os.path.join(workdir, "workspace.mxp")
    if os.path.exists(dst_filepath):
        return

    log = Logger.get_logger("create_workspace_mxp")
    max_script = default_mxp_template()
    if mxp_workspace:
        if not mxp_workspace.get("enabled_project_creation"):
            log.debug("3dsmax project creation is disabled.")
            return

        max_script = mxp_workspace.get("mxp_workspace_script")
        # Skip if mxp script in settings is empty
        if not max_script:
            log.debug("File 'workspace.mxp' not created. Settings value is empty.")
            return

    os.makedirs(workdir, exist_ok=True)
    with open(dst_filepath, "w") as mxp_file:
        mxp_file.write(max_script)

    return dst_filepath


def default_mxp_template():
    """Return text script for the path configuration if
    users do not enable project creation in AYON project
    setting
    """
    mxp_template = "\n".join((
        '[Directories]',
        'Animations= ./',
        'Archives=./',
        'AutoBackup=./',
        'BitmapProxies=./',
        'Fluid Simulations=./',
        'Images=./',
        'MaxStart=./',
        'Previews=./',
        'RenderAssets=./',
        'RenderOutput= ./renders/3dsmax',
        'Scenes=./',
        'Sounds=./',
        '[XReferenceDirs]',
        'Dir1=./'
    ))
    return mxp_template
