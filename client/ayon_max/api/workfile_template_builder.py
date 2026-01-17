"""3dsmax workfile template builder implementation"""
try:
    from pymxs import runtime as rt

except ImportError:
    rt = None

from ayon_core.pipeline import (
    registered_host,
    get_current_folder_path,
    AYON_INSTANCE_ID,
    AVALON_INSTANCE_ID,
)
from ayon_core.pipeline.workfile.workfile_template_builder import (
    AbstractTemplateBuilder,
)
from pathlib import Path


class MaxTemplateBuilder(AbstractTemplateBuilder):
    """Concrete implementation of AbstractTemplateBuilder for 3dsmax"""
    def import_template(self, path):
        """Import template into current scene.
        Block if a template is already loaded.

        Args:
            path (str): A path to current template (usually given by
            get_template_preset implementation)

        Returns:
            bool: Whether the template was successfully imported or not
        """
        filepath = Path(path)
        if not filepath.exists():
            return False
        rt.MergeMaxFile(
            filepath.as_posix(),
            rt.Name("deleteOldDups"),
            rt.Name("useMergedMtlDups"),
            quiet=True,
            includeFullGroup=True
        )
        max_objects = rt.getLastMergedNodes()
        if not max_objects:
            return True

        # update imported sets information
        folder_path = get_current_folder_path()
        for obj in max_objects:
            if rt.classOf(obj) == rt.Container:
                if rt.GetUserProp(obj, "id") in (
                    AYON_INSTANCE_ID, AVALON_INSTANCE_ID
                ):
                    continue
                if not rt.GetUserProp(obj, "folderPath"):
                    continue
            rt.setUserProp(obj, "folderPath", folder_path)
        return True

def build_workfile_template(*args):
    builder = MaxTemplateBuilder(registered_host())
    builder.build_template()


def update_workfile_template(*args):
    builder = MaxTemplateBuilder(registered_host())
    builder.rebuild_template()
