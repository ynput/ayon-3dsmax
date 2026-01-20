"""3dsmax workfile template builder implementation"""
import json
from pathlib import Path

try:
    from pymxs import runtime as rt

except ImportError:
    rt = None

from ayon_core.pipeline import registered_host
from ayon_core.pipeline.workfile.workfile_template_builder import (
    TemplateAlreadyImported,
    AbstractTemplateBuilder,
    PlaceholderPlugin,
    PlaceholderItem,
)
from ayon_core.tools.workfile_template_build import (
    WorkfileBuildPlaceholderDialog,
)

from .lib import (
    imprint,
    read,
    get_main_window,
    update_content_on_context_change,
)


PLACEHOLDER_SET = "PLACEHOLDERS_SET"


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
        if rt.getNodeByName(PLACEHOLDER_SET):
            raise TemplateAlreadyImported((
                "Build template already loaded\n"
                "Clean scene if needed (File > New Scene)"
            ))

        placeholder_container = rt.Container(name=PLACEHOLDER_SET)
        placeholder_container.isHidden = True

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
        update_content_on_context_change()
        return True


class MaxPlaceholderPlugin(PlaceholderPlugin):
    """Base Placeholder Plugin for 3ds Max with one unified cache.

    Creates a locator as placeholder node, which during populate provide
    all of its attributes defined on the locator's transform in
    `placeholder.data` and where `placeholder.scene_identifier` is the
    full path to the node.

    Inherited classes must still implement `populate_placeholder`

    """

    use_selection_as_parent = True
    item_class = PlaceholderItem

    def _create_placeholder_name(self, placeholder_data):
        return self.identifier.replace(".", "_")

    def _collect_scene_placeholders(self):
        nodes_by_identifier = self.builder.get_shared_populate_data(
            "placeholder_nodes"
        )
        if nodes_by_identifier is None:
            # Cache placeholder data to shared data
            nodes = [
                node for node in rt.Objects
                if rt.doesUserPropExist(node, "plugin_identifier")
            ]

            nodes_by_identifier = {}
            for node in nodes:
                identifier = rt.getUserProp(node, "plugin_identifier")
                nodes_by_identifier.setdefault(identifier, []).append(node)

            # Set the cache
            self.builder.set_shared_populate_data(
                "placeholder_nodes", nodes_by_identifier
            )

        return nodes_by_identifier

    def create_placeholder(self, placeholder_data):

        parent_object = None
        if self.use_selection_as_parent:
            selection = rt.getCurrentSelection()
            if len(selection) > 1:
                raise ValueError(
                    "More than one node is selected. "
                    "Please select only one to define the parent."
                )
            parent_object = selection[0] if selection else None

        placeholder_data["plugin_identifier"] = self.identifier
        placeholder_name = self._create_placeholder_name(placeholder_data)

        placeholder = rt.Container(name=placeholder_name)
        if parent_object:
            parent_object.children = placeholder
            imprinted_placeholder = parent_object.name
        else:
            imprinted_placeholder = placeholder.name

        self.imprint(imprinted_placeholder, placeholder_data)

    def update_placeholder(self, placeholder_item, placeholder_data):
        node_name = placeholder_item.scene_identifier

        changed_values = {}
        for key, value in placeholder_data.items():
            if value != placeholder_item.data.get(key):
                changed_values[key] = value

        # Delete attributes to ensure we imprint new data with correct type
        target_node = rt.getNodeByName(node_name)
        for key in changed_values.keys():
            placeholder_item.data[key] = value
            if rt.getUserProp(target_node, key) is not None:
                rt.deleteUserProp(target_node, key)

        self.imprint(node_name, changed_values)

    def collect_placeholders(self):
        placeholders = []
        nodes_by_identifier = self._collect_scene_placeholders()
        for node in nodes_by_identifier.get(self.identifier, []):
            # TODO do data validations and maybe upgrades if they are invalid
            placeholder_data = self.read(node)
            placeholders.append(
                self.item_class(scene_identifier=node,
                                data=placeholder_data,
                                plugin=self)
            )

        return placeholders

    def post_placeholder_process(self, placeholder, failed):
        """Cleanup placeholder after load of its corresponding representations.

        Hide placeholder, add them to placeholder set.
        Used only by PlaceholderCreateMixin and PlaceholderLoadMixin

        Args:
            placeholder (PlaceholderItem): Item which was just used to load
                representation.
            failed (bool): Loading of representation failed.
        """
        # Hide placeholder and add them to placeholder set
        node = placeholder.scene_identifier

        # If we just populate the placeholders from current scene, the
        # placeholder set will not be created so account for that.
        placeholder_set = rt.getNodebyName(PLACEHOLDER_SET)
        if placeholder_set:
            placeholder_set = rt.Container(name=PLACEHOLDER_SET)
        placeholder_set.children = node
        node.isHidden = True

    def delete_placeholder(self, placeholder):
        """Remove placeholder if building was successful

        Used only by PlaceholderCreateMixin and PlaceholderLoadMixin.
        """
        node = placeholder.scene_identifier
        node_to_removed = rt.getNodeByName(node)
        if node_to_removed:
            rt.Delete(node_to_removed)

    def imprint(self, node, data):
        """Imprint call for placeholder node"""

        # Complicated data that can't be represented as flat 3dsmax attributes
        # we write to json strings, e.g. multiselection EnumDef
        for key, value in data.items():
            if isinstance(value, (list, tuple, dict)):
                data[key] = "JSON::{}".format(json.dumps(value))

        imprint(node, data)

    def read(self, node):
        """Read call for placeholder node"""

        data = read(node)

        # Complicated data that can't be represented as flat 3dsmax attributes
        # we read from json strings, e.g. multiselection EnumDef
        for key, value in data.items():
            if isinstance(value, str) and value.startswith("JSON::"):
                value = value[len("JSON::"):]   # strip of JSON:: prefix
                data[key] = json.loads(value)

        return data

def build_workfile_template(*args) -> None:
    """Build the workfile template for 3ds Max."""
    builder = MaxTemplateBuilder(registered_host())
    builder.build_template()


def update_workfile_template(*args) -> None:
    """Update the workfile template for 3ds Max."""
    builder = MaxTemplateBuilder(registered_host())
    builder.rebuild_template()


def create_placeholder(*args) -> None:
    """Create Workfile Placeholder for 3ds Max."""
    host = registered_host()
    builder = MaxTemplateBuilder(host)
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.show()


def update_placeholder(*args) -> None:
    """Update Workfile Placeholder for 3ds Max."""
    host = registered_host()
    builder = MaxTemplateBuilder(host)
    placeholder_items_by_id = {
        placeholder_item.scene_identifier: placeholder_item
        for placeholder_item in builder.get_placeholders()
    }
    placeholder_items = []
    for node in rt.getCurrentSelection():
        if node.name in placeholder_items_by_id:
            placeholder_items.append(placeholder_items_by_id[node.name])

    # TODO show UI at least
    if len(placeholder_items) == 0:
        raise ValueError("No node selected")

    if len(placeholder_items) > 1:
        raise ValueError("Too many selected nodes")

    placeholder_item = placeholder_items[0]
    window = WorkfileBuildPlaceholderDialog(host, builder,
                                            parent=get_main_window())
    window.set_update_mode(placeholder_item)
    window.exec_()
