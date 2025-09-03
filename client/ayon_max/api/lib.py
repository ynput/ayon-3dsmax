# -*- coding: utf-8 -*-
"""Library of functions useful for 3dsmax pipeline."""
import os
import contextlib
import logging
import json
from functools import partial
from typing import Any, Dict, Union

from ayon_core.pipeline import (
    get_current_project_name,
    get_current_folder_path,
    get_current_task_name,
    colorspace,
)
from ayon_core.tools.utils import SimplePopup
from ayon_core.settings import get_project_settings
from ayon_core.pipeline.context_tools import (
    get_current_task_entity
)
from ayon_core.style import load_stylesheet
from pymxs import runtime as rt


JSON_PREFIX = "JSON::"
log = logging.getLogger("ayon_max")


def get_main_window():
    """Acquire Max's main window"""
    from qtpy import QtWidgets
    top_widgets = QtWidgets.QApplication.topLevelWidgets()
    name = "QmaxApplicationWindow"
    for widget in top_widgets:
        if (
            widget.inherits("QMainWindow")
            and widget.metaObject().className() == name
        ):
            return widget
    raise RuntimeError('Count not find 3dsMax main window.')


def imprint(node_name: str, data: dict) -> bool:
    node = rt.GetNodeByName(node_name)
    if not node:
        return False

    for k, v in data.items():
        if isinstance(v, (dict, list)):
            rt.SetUserProp(node, k, f"{JSON_PREFIX}{json.dumps(v)}")
        else:
            rt.SetUserProp(node, k, v)

    return True


def lsattr(
        attr: str,
        value: Union[str, None] = None,
        root: Union[str, None] = None) -> list:
    """List nodes having attribute with specified value.

    Args:
        attr (str): Attribute name to match.
        value (str, Optional): Value to match, of omitted, all nodes
            with specified attribute are returned no matter of value.
        root (str, Optional): Root node name. If omitted, scene root is used.

    Returns:
        list of nodes.
    """
    root = rt.RootNode if root is None else rt.GetNodeByName(root)

    def output_node(node, nodes):
        nodes.append(node)
        for child in node.Children:
            output_node(child, nodes)

    nodes = []
    output_node(root, nodes)
    return [
        n for n in nodes
        if rt.GetUserProp(n, attr) == value
    ] if value else [
        n for n in nodes
        if rt.GetUserProp(n, attr)
    ]


def read(container) -> dict:
    data = {}
    props = rt.GetUserPropBuffer(container)
    # this shouldn't happen but let's guard against it anyway
    if not props:
        return data

    for line in props.split("\r\n"):
        try:
            key, value = line.split("=")
        except ValueError:
            # if the line cannot be split we can't really parse it
            continue

        value = value.strip()
        if isinstance(value.strip(), str) and \
                value.startswith(JSON_PREFIX):
            with contextlib.suppress(json.JSONDecodeError):
                value = json.loads(value[len(JSON_PREFIX):])

        # default value behavior
        # convert maxscript boolean values
        if value == "true":
            value = True
        elif value == "false":
            value = False

        data[key.strip()] = value

    data["instance_node"] = container.Name

    return data


@contextlib.contextmanager
def maintained_selection():
    previous_selection = rt.GetCurrentSelection()
    try:
        yield
    finally:
        if previous_selection:
            rt.Select(previous_selection)
        else:
            rt.Select()


def get_all_children(parent, node_type=None):
    """Handy function to get all the children of a given node

    Args:
        parent (3dsmax Node1): Node to get all children of.
        node_type (None, runtime.class): give class to check for
            e.g. rt.FFDBox/rt.GeometryClass etc.

    Returns:
        list: list of all children of the parent node
    """
    def list_children(node):
        children = []
        for c in node.Children:
            children.append(c)
            children = children + list_children(c)
        return children
    child_list = list_children(parent)

    return ([x for x in child_list if rt.SuperClassOf(x) == node_type]
            if node_type else child_list)


def get_current_renderer():
    """
    Notes:
        Get current renderer for Max

    Returns:
        "{Current Renderer}:{Current Renderer}"
        e.g. "Redshift_Renderer:Redshift_Renderer"
    """
    return rt.renderers.production


def get_default_render_folder(project_setting=None):
    return (project_setting["max"]
                           ["RenderSettings"]
                           ["default_render_image_folder"])


def set_render_frame_range(start_frame, end_frame):
    """
    Note:
        Frame range can be specified in different types. Possible values are:
        * `1` - Single frame.
        * `2` - Active time segment ( animationRange ).
        * `3` - User specified Range.
        * `4` - User specified Frame pickup string (for example `1,3,5-12`).

    Todo:
        Current type is hard-coded, there should be a custom setting for this.
    """
    rt.rendTimeType = 3
    if start_frame is not None and end_frame is not None:
        rt.rendStart = int(start_frame)
        rt.rendEnd = int(end_frame)


def get_multipass_setting(project_setting=None):
    return (project_setting["max"]
                           ["RenderSettings"]
                           ["multipass"])


def set_scene_resolution(width: int, height: int):
    """Set the render resolution

    Args:
        width(int): value of the width
        height(int): value of the height

    Returns:
        None

    """
    # make sure the render dialog is closed
    # for the update of resolution
    # Changing the Render Setup dialog settings should be done
    # with the actual Render Setup dialog in a closed state.
    if rt.renderSceneDialog.isOpen():
        rt.renderSceneDialog.close()

    rt.renderWidth = width
    rt.renderHeight = height


def reset_scene_resolution(task_entity=None):
    """Apply the scene resolution from the project definition

    scene resolution can be overwritten by a folder if the folder.attrib
    contains any information regarding scene resolution.
    """
    if task_entity is None:
        task_entity = get_current_task_entity(fields={"attrib"})
    task_attributes = task_entity["attrib"]
    width = int(task_attributes["resolutionWidth"])
    height = int(task_attributes["resolutionHeight"])

    set_scene_resolution(width, height)


def get_frame_range(task_entity=None) -> Union[Dict[str, Any], None]:
    """Get the current task frame range and handles

    Args:
        task_entity (dict): Task Entity.

    Returns:
        dict: with frame start, frame end, handle start, handle end.
    """
    # Set frame start/end
    if task_entity is None:
        task_entity = get_current_task_entity(fields={"attrib"})
    task_attributes = task_entity["attrib"]
    frame_start = int(task_attributes["frameStart"])
    frame_end = int(task_attributes["frameEnd"])
    handle_start = int(task_attributes["handleStart"])
    handle_end = int(task_attributes["handleEnd"])
    frame_start_handle = frame_start - handle_start
    frame_end_handle = frame_end + handle_end

    return {
        "frameStart": frame_start,
        "frameEnd": frame_end,
        "handleStart": handle_start,
        "handleEnd": handle_end,
        "frameStartHandle": frame_start_handle,
        "frameEndHandle": frame_end_handle,
    }


def reset_frame_range(fps: bool = True):
    """Set frame range to current folder.
    This is part of 3dsmax documentation:

    animationRange: A System Global variable which lets you get and
        set an Interval value that defines the start and end frames
        of the Active Time Segment.
    frameRate: A System Global variable which lets you get
            and set an Integer value that defines the current
            scene frame rate in frames-per-second.
    """
    if fps:
        rt.frameRate = float(get_fps_for_current_context())

    frame_range = get_frame_range()

    set_timeline(
        frame_range["frameStartHandle"], frame_range["frameEndHandle"])
    set_render_frame_range(
        frame_range["frameStartHandle"], frame_range["frameEndHandle"])

    project_name = get_current_project_name()
    settings = get_project_settings(project_name).get("max")
    auto_key_default_key_time = settings.get(
        "auto_key_default", {}).get("defualt_key_time")
    rt.maxOps.autoKeyDefaultKeyTime = auto_key_default_key_time


def get_fps_for_current_context():
    """Get fps that should be set for current context.

    Todos:
        - Skip project value.
        - Merge logic with 'get_frame_range' and 'reset_scene_resolution' ->
            all the values in the functions can be collected at one place as
            they have same requirements.

    Returns:
        Union[int, float]: FPS value.
    """
    task_entity = get_current_task_entity(fields={"attrib"})
    return task_entity["attrib"]["fps"]


def validate_unit_scale(project_settings=None):
    """Apply the unit scale setting to 3dsMax
    """

    if is_headless():
        return
    if project_settings is None:
        project_name = get_current_project_name()
        project_settings = get_project_settings(project_name).get("max")
    scene_scale_enabled = project_settings["unit_scale_settings"]["enabled"]
    if not scene_scale_enabled:
        log.info("Using default scale display type.")
        rt.units.DisplayType = rt.Name("Generic")
        return
    scene_scale = project_settings["unit_scale_settings"]["scene_unit_scale"]
    if rt.units.DisplayType == rt.Name("Metric") and (
        rt.units.MetricType == rt.Name(scene_scale)
    ):
        return

    parent = get_main_window()
    dialog = SimplePopup(parent=parent)
    dialog.setWindowTitle("Wrong Unit Scale")
    dialog.set_message("Scene units do not match studio/project preferences.")
    dialog.set_button_text("Fix")
    dialog.setStyleSheet(load_stylesheet())

    dialog.on_clicked.connect(partial(set_unit_scale, project_settings))
    dialog.show()


def set_unit_scale(project_settings=None):
    """Function to set unit scale in Metric
    """
    if project_settings is None:
        project_name = get_current_project_name()
        project_settings = get_project_settings(project_name).get("max")
    scene_scale = project_settings["unit_scale_settings"]["scene_unit_scale"]
    rt.units.DisplayType = rt.Name("Metric")
    rt.units.MetricType = rt.Name(scene_scale)


def convert_unit_scale():
    """Convert system unit scale in 3dsMax
    for fbx export

    Returns:
        str: unit scale
    """
    unit_scale_dict = {
        "millimeters": "mm",
        "centimeters": "cm",
        "meters": "m",
        "kilometers": "km"
    }
    current_unit_scale = rt.Execute("units.MetricType as string")
    return unit_scale_dict[current_unit_scale]


def set_context_setting():
    """Apply the project settings from the project definition

    Settings can be overwritten by an folder if the folder.attrib contains
    any information regarding those settings.

    Examples of settings:
        frame range
        resolution

    Returns:
        None
    """
    reset_scene_resolution()
    reset_frame_range()
    validate_unit_scale()
    reset_colorspace()


def get_max_version():
    """
    Args:
    get max version date for deadline

    Returns:
        #(25000, 62, 0, 25, 0, 0, 997, 2023, "")
        max_info[7] = max version date
    """
    max_info = rt.MaxVersion()
    return max_info[7]


def is_headless():
    """Check if 3dsMax runs in batch mode.
    If it returns True, it runs in 3dsbatch.exe
    If it returns False, it runs in 3dsmax.exe
    """
    return rt.maxops.isInNonInteractiveMode()


def set_timeline(frameStart, frameEnd):
    """Set frame range for timeline editor in Max
    """
    rt.animationRange = rt.interval(int(frameStart), int(frameEnd))
    return rt.animationRange


def reset_colorspace():
    """OCIO Configuration
    Supports in 3dsMax 2024+

    """
    if int(get_max_version()) < 2024:
        return
    colorspace_mgr = rt.ColorPipelineMgr
    ocio_config_path = os.getenv("OCIO")
    colorspace_mgr.Mode = rt.Name("OCIO_EnvVar")
    if not ocio_config_path:
        max_config_data = colorspace.get_current_context_imageio_config_preset()
        if max_config_data:
            ocio_config_path = max_config_data["path"]
            colorspace_mgr.Mode = rt.Name("OCIO_Custom")
            colorspace_mgr.OCIOConfigPath = ocio_config_path


def check_colorspace():
    parent = get_main_window()
    if parent is None:
        log.info("Skipping outdated pop-up "
                 "because Max main window can't be found.")
    if int(get_max_version()) >= 2024:
        color_mgr = rt.ColorPipelineMgr
        max_config_data = colorspace.get_current_context_imageio_config_preset()
        if max_config_data and color_mgr.Mode != rt.Name("OCIO_Custom"):
            if not is_headless():
                dialog = SimplePopup(parent=parent)
                dialog.setWindowTitle("Warning: Wrong OCIO Mode")
                dialog.set_message("This scene has wrong OCIO "
                                  "Mode setting.")
                dialog.set_button_text("Fix")
                dialog.setStyleSheet(load_stylesheet())
                dialog.on_clicked.connect(reset_colorspace)
                dialog.show()


def get_context_label():
    return "{}, {}".format(
        get_current_folder_path(),
        get_current_task_name()
    )


def unique_namespace(namespace, format="%02d",
                     prefix="", suffix="", con_suffix="CON"):
    """Return unique namespace

    Arguments:
        namespace (str): Name of namespace to consider
        format (str, optional): Formatting of the given iteration number
        suffix (str, optional): Only consider namespaces with this suffix.
        con_suffix: max only, for finding the name of the master container

    >>> unique_namespace("bar")
    # bar01
    >>> unique_namespace(":hello")
    # :hello01
    >>> unique_namespace("bar:", suffix="_NS")
    # bar01_NS:

    """

    def current_namespace():
        current = namespace
        # When inside a namespace Max adds no trailing :
        if not current.endswith(":"):
            current += ":"
        return current

    # Always check against the absolute namespace root
    # There's no clash with :x if we're defining namespace :a:x
    ROOT = ":" if namespace.startswith(":") else current_namespace()

    # Strip trailing `:` tokens since we might want to add a suffix
    start = ":" if namespace.startswith(":") else ""
    end = ":" if namespace.endswith(":") else ""
    namespace = namespace.strip(":")
    if ":" in namespace:
        # Split off any nesting that we don't uniqify anyway.
        parents, namespace = namespace.rsplit(":", 1)
        start += parents + ":"
        ROOT += start

    iteration = 1
    increment_version = True
    while increment_version:
        nr_namespace = namespace + format % iteration
        unique = prefix + nr_namespace + suffix
        container_name = f"{unique}:{namespace}{con_suffix}"
        if not rt.getNodeByName(container_name):
            name_space = start + unique + end
            increment_version = False
            return name_space
        else:
            increment_version = True
        iteration += 1


def get_namespace(container_name):
    """Get the namespace and name of the sub-container

    Args:
        container_name (str): the name of master container

    Raises:
        RuntimeError: when there is no master container found

    Returns:
        namespace (str): namespace of the sub-container
        name (str): name of the sub-container
    """
    node = rt.getNodeByName(container_name)
    if not node:
        raise RuntimeError("Master Container Not Found..")
    name = rt.getUserProp(node, "name")
    namespace = rt.getUserProp(node, "namespace")
    return namespace, name


def object_transform_set(container_children):
    """A function which allows to store the transform of
    previous loaded object(s)
    Args:
        container_children(list): A list of nodes

    Returns:
        transform_set (dict): A dict with all transform data of
        the previous loaded object(s)
    """
    transform_set = {}
    for node in container_children:
        name = f"{node}.transform"
        transform_set[name] = node.pos
        name = f"{node}.scale"
        transform_set[name] = node.scale
    return transform_set


def get_plugins() -> list:
    """Get all loaded plugins in 3dsMax

    Returns:
        plugin_info_list: a list of loaded plugins
    """
    manager = rt.PluginManager
    count = manager.pluginDllCount
    plugin_info_list = []
    for p in range(1, count + 1):
        plugin_info = manager.pluginDllName(p)
        plugin_info_list.append(plugin_info)

    return plugin_info_list


def update_modifier_node_names(event, node):
    """Update the name of the nodes after renaming

    Args:
        event (pymxs.MXSWrapperBase): Event Name (
            Mandatory argument for rt.NodeEventCallback)
        node (list): Event Number (
            Mandatory argument for rt.NodeEventCallback)

    """
    containers = [
        obj
        for obj in rt.Objects
        if (
            rt.ClassOf(obj) == rt.Container
            and rt.getUserProp(obj, "id") == "pyblish.avalon.instance"
            and rt.getUserProp(obj, "productType") not in {
                "workfile", "tyflow"
            }
        )
    ]
    if not containers:
        return
    for container in containers:
        ayon_data = container.modifiers[0].openPypeData
        updated_node_names = [str(node.node) for node
                              in ayon_data.all_handles]
        rt.setProperty(ayon_data, "sel_list", updated_node_names)


@contextlib.contextmanager
def render_resolution(width, height):
    """Set render resolution option during context

    Args:
        width (int): render width
        height (int): render height
    """
    current_renderWidth = rt.renderWidth
    current_renderHeight = rt.renderHeight
    try:
        rt.renderWidth = width
        rt.renderHeight = height
        yield
    finally:
        rt.renderWidth = current_renderWidth
        rt.renderHeight = current_renderHeight


def get_tyflow_export_operators():
    """Get Tyflow Export Particles Operators.

    Returns:
        list: Particle operators

    """
    operators = []
    members = [obj for obj in rt.Objects if rt.ClassOf(obj) == rt.tyFlow]
    for member in members:
        obj = member.baseobject
        anim_names = rt.GetSubAnimNames(obj)
        for anim_name in anim_names:
            sub_anim = rt.GetSubAnim(obj, anim_name)
            if not rt.isKindOf(sub_anim, rt.tyEvent):
                continue
            node_names = rt.GetSubAnimNames(sub_anim)
            for node_name in node_names:
                node_sub_anim = rt.GetSubAnim(sub_anim, node_name)
                if rt.hasProperty(node_sub_anim, "exportMode"):
                    operators.append(node_sub_anim)
    return operators


@contextlib.contextmanager
def suspended_refresh():
    """Suspended refresh for scene and modify panel redraw.
    """
    if is_headless():
        yield
        return
    rt.disableSceneRedraw()
    rt.suspendEditing()
    try:
        yield

    finally:
        rt.enableSceneRedraw()
        rt.resumeEditing()
