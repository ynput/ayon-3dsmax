# -*- coding: utf-8 -*-
"""Pipeline tools for AYON 3ds max integration."""
import os
import logging
from operator import attrgetter

import json

from ayon_core.host import HostBase, IWorkfileHost, ILoadHost, IPublishHost

from ayon_core.lib import register_event_callback
import pyblish.api
from ayon_core.pipeline import (
    register_creator_plugin_path,
    register_loader_plugin_path,
    AVALON_CONTAINER_ID,
    AYON_CONTAINER_ID,
    get_current_project_name
)
from ayon_max.api.menu import AYONMenu
from ayon_core.settings import get_project_settings
from ayon_max.api import lib
from ayon_max.api.plugin import MS_CUSTOM_ATTRIB
from ayon_max import MAX_HOST_DIR

from pymxs import runtime as rt  # noqa

log = logging.getLogger("ayon_max")

PLUGINS_DIR = os.path.join(MAX_HOST_DIR, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")


class MaxHost(HostBase, IWorkfileHost, ILoadHost, IPublishHost):

    name = "max"
    menu = None

    def __init__(self):
        super(MaxHost, self).__init__()
        self._op_events = {}
        self._has_been_setup = False

    def get_app_information(self):
        from ayon_core.host import ApplicationInformation

        (
            _rel_number,
            _api_version,
            _rel_rev_number,

            _major_version,
            _update_version,
            _hotfix_number,
            _build_number,

            year_version,
            product_version,
        ) = rt.maxVersion()
        version = f"{year_version}{product_version}"
        return ApplicationInformation(
            app_name="3ds Max",
            app_version=version,
        )

    def install(self):
        pyblish.api.register_host("max")

        pyblish.api.register_plugin_path(PUBLISH_PATH)
        register_loader_plugin_path(LOAD_PATH)
        register_creator_plugin_path(CREATE_PATH)

        _set_project()
        _set_autobackup_dir()

        self.menu = AYONMenu()

        register_event_callback("workfile.open.before", on_before_open)
        register_event_callback("workfile.open.after", on_after_open)
        register_event_callback("before.save", before_save)
        register_event_callback("taskChanged", self.on_task_changed)
        self._has_been_setup = True
        self._register_callbacks()

    def workfile_has_unsaved_changes(self):
        return rt.getSaveRequired()

    def get_workfile_extensions(self):
        return [".max"]

    def save_workfile(self, dst_path=None):
        rt.saveMaxFile(dst_path)
        return dst_path

    def open_workfile(self, filepath):
        rt.checkForSave()
        rt.loadMaxFile(filepath)
        return filepath

    def get_current_workfile(self):
        return os.path.join(rt.maxFilePath, rt.maxFileName)

    def get_containers(self):
        return ls()

    def _register_callbacks(self):
        rt.callbacks.removeScripts(id=rt.name("AyonCallbacks"))
        rt.callbacks.addScript(
            rt.Name('welcomeScreenDone'),
            on_new, id=rt.name("AyonCallbacks")
        )
        rt.callbacks.addScript(
            rt.Name('systemPostNew'),
            lib.set_context_setting,
            id=rt.name("AyonCallbacks")
        )
        rt.callbacks.addScript(
            rt.Name('postWorkspaceChange'),
            self._deferred_menu_creation,
            id=rt.name("AyonCallbacks"))
        rt.NodeEventCallback(
            nameChanged=lib.update_modifier_node_names)

    def _deferred_menu_creation(self):
        self.log.info("Building menu ...")
        self.menu = AYONMenu()

    @staticmethod
    def create_context_node():
        """Helper for creating context holding node."""

        root_scene = rt.rootScene

        create_attr_script = ("""
attributes "OpenPypeContext"
(
    parameters main rollout:params
    (
        context type: #string
    )

    rollout params "OpenPype Parameters"
    (
        editText editTextContext "Context" type: #string
    )
)
        """)

        attr = rt.execute(create_attr_script)
        rt.custAttributes.add(root_scene, attr)

        return root_scene.OpenPypeContext.context

    def update_context_data(self, data, changes):
        try:
            _ = rt.rootScene.OpenPypeContext.context
        except AttributeError:
            # context node doesn't exists
            self.create_context_node()

        rt.rootScene.OpenPypeContext.context = json.dumps(data)

    def get_context_data(self):
        try:
            context = rt.rootScene.OpenPypeContext.context
        except AttributeError:
            # context node doesn't exists
            context = self.create_context_node()
        if not context:
            context = "{}"
        return json.loads(context)

    def on_task_changed(self):
        if lib.is_headless():
            return

        ayon_menu = self.menu.menu
        if ayon_menu is not None:
            actions = ayon_menu.actions()
            context_action = actions[0]
            context_label = lib.get_context_label()
            context_action.setText(f"{context_label}")


def parse_container(container):
    """Return the container node's full container data.

    Args:
        container (str): A container node name.

    Returns:
        dict: The container schema data for this container node.

    """
    data = lib.read(container)

    # Backwards compatibility pre-schemas for containers
    data["schema"] = data.get("schema", "openpype:container-3.0")

    # Append transient data
    data["objectName"] = container.Name
    return data


def ls():
    """Get all AYON containers."""
    objs = rt.objects
    containers = [
        obj for obj in objs
        if rt.getUserProp(obj, "id") in {
            AYON_CONTAINER_ID, AVALON_CONTAINER_ID
        }
    ]

    for container in sorted(containers, key=attrgetter("name")):
        yield parse_container(container)


def on_new():
    if not os.path.exists(rt.ColorPipelineMgr.OCIOConfigPath):
        lib.reset_colorspace()
    last_workfile = os.getenv("AYON_LAST_WORKFILE")
    if os.getenv("AVALON_OPEN_LAST_WORKFILE") != "1"  \
        or not os.path.exists(last_workfile):
            lib.set_context_setting()


def containerise(name: str, nodes: list, context,
                 namespace=None, loader=None, suffix="_CON"):
    data = {
        "schema": "openpype:container-2.0",
        "id": AVALON_CONTAINER_ID,
        "name": name,
        "namespace": namespace or "",
        "loader": loader,
        "representation": context["representation"]["id"],
        "project_name": context["project"]["name"]
    }
    container_name = f"{namespace}:{name}{suffix}"
    container = rt.container(name=container_name)
    import_custom_attribute_data(container, nodes)
    if not lib.imprint(container_name, data):
        print(f"imprinting of {container_name} failed.")
    return container



def containerise_texture(name: str, context: dict,
                         view_node, sme_view,
                         namespace=None, loader=None,
                         suffix="_CON"):
    """Containerise texture nodes

    Args:
        name (str): name of the container
        context (dict): context
        view_node: texture node
        sme_view: target view of slate material editor
        namespace (str, optional): namespace. Defaults to None.
        loader (str, optional): loader. Defaults to None.
        suffix (str, optional): suffix. Defaults to "_CON".

    Returns:
        container: The container object holding the texture node metadata.
    """
    data = {
        "schema": "ayon:container-3.0",
        "id": AYON_CONTAINER_ID,
        "name": name,
        "namespace": namespace or "",
        "loader": loader,
        "representation": context["representation"]["id"],
        "project_name": context["project"]["name"],
        "view_node": view_node,
        "sme_view": sme_view,
    }
    container_name = f"{namespace}:{name}{suffix}"
    container = rt.container(name=container_name)
    if not lib.imprint(container_name, data):
        print(f"imprinting of {container_name} failed.")
    return container


def _set_project():
    project_name = get_current_project_name()
    project_settings = get_project_settings(project_name)
    enable_project_creation = project_settings["max"].get("enabled_project_creation")
    if not enable_project_creation:
        log.debug("Project creation disabled. Skipping project creation.")
        return

    workdir = os.getenv("AYON_WORKDIR")
    os.makedirs(workdir, exist_ok=True)
    rt.pathConfig.setCurrentProjectFolder(workdir)

    mxp_filepath = os.path.join(workdir, "workspace.mxp")
    if os.path.exists(mxp_filepath):
        rt.pathConfig.load(mxp_filepath)
        directory_count = rt.pathConfig.getProjectSubDirectoryCount()
        for count in range(directory_count):
            proj_dir = rt.pathConfig.getProjectSubDirectory(count)
            if proj_dir:
                os.makedirs(proj_dir, exist_ok=True)

    # avoid glitching viewport
    rt.viewport.ResetAllViews()


def _set_autobackup_dir():
    """Set up autobackup folder to avoid non-existing directory
    """
    autobackup_dir = rt.pathConfig.GetDir(rt.Name("autoback"))
    os.makedirs(autobackup_dir, exist_ok=True)


def on_before_open():
    """Check and set up project before opening workfile
    """
    _set_project()


def on_after_open():
    """Check and set up unit scale after opening workfile if user enabled.
    """
    lib.validate_unit_scale()


def before_save(event):
    """Check and set up project before saving workfile
    """
    max_filename_before: str = rt.maxFileName
    max_filename_after: str = event.get("filename")

    if not max_filename_before:
        # Saving from a new unsaved file, no need to check for changes.
        return

    if max_filename_before != max_filename_after:
        print(f"Detected scene name change from {max_filename_before} to "
              f"{max_filename_after}")
    max_filename_before = os.path.splitext(max_filename_before)[0]
    max_filename_after = os.path.splitext(max_filename_after)[0]
    lib.reset_render_outputs(max_filename_before, max_filename_after)


def load_custom_attribute_data():
    """Re-loading the AYON custom parameter built by the creator

    Returns:
        attribute: re-loading the custom OP attributes set in Maxscript
    """
    return rt.Execute(MS_CUSTOM_ATTRIB)


def import_custom_attribute_data(container: str, selections: list):
    """Importing the Openpype/AYON custom parameter built by the creator

    Args:
        container (str): target container which adds custom attributes
        selections (list): nodes to be added into
        group in custom attributes
    """
    attrs = load_custom_attribute_data()
    modifier = rt.EmptyModifier()
    rt.addModifier(container, modifier)
    container.modifiers[0].name = "OP Data"
    rt.custAttributes.add(container.modifiers[0], attrs)
    node_list = []
    sel_list = []
    for i in selections:
        node_ref = rt.NodeTransformMonitor(node=i)
        node_list.append(node_ref)
        sel_list.append(str(i))

    # Setting the property
    rt.setProperty(
        container.modifiers[0].openPypeData,
        "all_handles", node_list)
    rt.setProperty(
        container.modifiers[0].openPypeData,
        "sel_list", sel_list)


def update_custom_attribute_data(container: str, selections: list):
    """Updating the AYON custom parameter built by the creator

    Args:
        container (str): target container which adds custom attributes
        selections (list): nodes to be added into
        group in custom attributes
    """
    if container.modifiers[0].name == "OP Data":
        rt.deleteModifier(container, container.modifiers[0])
    import_custom_attribute_data(container, selections)


def get_previous_loaded_object(container: str):
    """Get previous loaded_object through the OP data

    Args:
        container (str): the container which stores the OP data

    Returns:
        node_list(list): list of nodes which are previously loaded
    """
    node_list = []
    node_transform_monitor_list = rt.getProperty(
        container.modifiers[0].openPypeData, "all_handles")
    for node_transform_monitor in node_transform_monitor_list:
        node_list.append(node_transform_monitor.node)
    return node_list


def remove_container_data(container_node: str):
    """Function to remove container data after updating, switching or deleting it.

    Args:
        container_node (str): container node
    """
    if container_node.modifiers[0].name == "OP Data":
        all_set_members_names = [
            member.node for member
            in container_node.modifiers[0].openPypeData.all_handles]
        # clean up the children of alembic dummy objects
        for current_set_member in all_set_members_names:
            shape_list = [members for members in current_set_member.Children
                          if rt.ClassOf(members) == rt.AlembicObject
                          or rt.isValidNode(members)]
            if shape_list:  # noqa
                rt.Delete(shape_list)
            rt.Delete(current_set_member)
        rt.deleteModifier(container_node, container_node.modifiers[0])

    rt.Delete(container_node)
    rt.redrawViews()
