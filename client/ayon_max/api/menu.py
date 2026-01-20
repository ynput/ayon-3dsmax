# -*- coding: utf-8 -*-
"""3dsmax menu definition of AYON."""
import os
from qtpy import QtWidgets, QtCore


try:
    from pymxs import runtime as rt

except ImportError:
    rt = None


from ayon_core.tools.utils import host_tools
from ayon_core.settings import get_project_settings
from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline.workfile import save_next_version
from ayon_max.api import lib
from .workfile_template_builder import (
    build_workfile_template,
    update_workfile_template,
    create_placeholder,
    update_placeholder
)


class AYONMenu(object):
    """Object representing AYON menu.

    This is using "hack" to inject itself before "Help" menu of 3dsmax.
    For some reason `postLoadingMenus` event doesn't fire, and main menu
    if probably re-initialized by menu templates, se we wait for at least
    1 event Qt event loop before trying to insert.

    """

    def __init__(self):
        super().__init__()
        self.main_widget = self.get_main_widget()
        self.menu = None

        timer = QtCore.QTimer()
        # set number of event loops to wait.
        timer.setInterval(1)
        timer.timeout.connect(self._on_timer)
        timer.start()

        self._timer = timer
        self._counter = 0

    def _on_timer(self):
        if self._counter < 1:
            self._counter += 1
            return

        self._counter = 0
        self._timer.stop()
        self._build_ayon_menu()

    @staticmethod
    def get_main_widget():
        """Get 3dsmax main window."""
        return QtWidgets.QWidget.find(rt.windows.getMAXHWND())

    def get_main_menubar(self) -> QtWidgets.QMenuBar:
        """Get main Menubar by 3dsmax main window."""
        return list(self.main_widget.findChildren(QtWidgets.QMenuBar))[0]

    def _get_or_create_ayon_menu(
            self, name: str = "&AYON",
            before: str = "&Help") -> QtWidgets.QAction:
        """Create AYON menu.

        Args:
            name (str, Optional): AYON menu name.
            before (str, Optional): Name of the 3dsmax main menu item to
                add AYON menu before.

        Returns:
            QtWidgets.QAction: AYON menu action.

        """
        if self.menu is not None:
            return self.menu

        menu_bar = self.get_main_menubar()
        menu_items = menu_bar.findChildren(
            QtWidgets.QMenu, options=QtCore.Qt.FindDirectChildrenOnly)
        help_action = None
        for item in menu_items:
            if name in item.title():
                # we already have AYON menu
                return item

            if before in item.title():
                help_action = item.menuAction()
        tab_menu_label = os.environ.get("AYON_MENU_LABEL") or "AYON"
        op_menu = QtWidgets.QMenu("&{}".format(tab_menu_label))
        menu_bar.insertMenu(help_action, op_menu)

        self.menu = op_menu
        return op_menu

    def _build_ayon_menu(self) -> QtWidgets.QAction:
        """Build items in AYON menu."""
        ayon_menu = self._get_or_create_ayon_menu()

        context_label = lib.get_context_label()
        context_action = QtWidgets.QAction(f"{context_label}", ayon_menu)
        context_action.setEnabled(False)
        ayon_menu.addAction(context_action)

        project_name = get_current_project_name()
        project_settings = get_project_settings(project_name)
        if project_settings["core"]["tools"]["ayon_menu"].get(
            "version_up_current_workfile"):
            version_up_action = QtWidgets.QAction("Version Up Workfile", ayon_menu)
            version_up_action.triggered.connect(self.version_up_callback)

            ayon_menu.addSeparator()
            ayon_menu.addAction(version_up_action)

        ayon_menu.addSeparator()

        load_action = QtWidgets.QAction("Load...", ayon_menu)
        load_action.triggered.connect(self.load_callback)
        ayon_menu.addAction(load_action)

        publish_action = QtWidgets.QAction("Publish...", ayon_menu)
        publish_action.triggered.connect(self.publish_callback)
        ayon_menu.addAction(publish_action)

        manage_action = QtWidgets.QAction("Manage...", ayon_menu)
        manage_action.triggered.connect(self.manage_callback)
        ayon_menu.addAction(manage_action)

        library_action = QtWidgets.QAction("Library...", ayon_menu)
        library_action.triggered.connect(self.library_callback)
        ayon_menu.addAction(library_action)

        ayon_menu.addSeparator()

        workfiles_action = QtWidgets.QAction("Work Files...", ayon_menu)
        workfiles_action.triggered.connect(self.workfiles_callback)
        ayon_menu.addAction(workfiles_action)

        ayon_menu.addSeparator()

        res_action = QtWidgets.QAction("Set Resolution", ayon_menu)
        res_action.triggered.connect(self.resolution_callback)
        ayon_menu.addAction(res_action)

        frame_action = QtWidgets.QAction("Set Frame Range", ayon_menu)
        frame_action.triggered.connect(self.frame_range_callback)
        ayon_menu.addAction(frame_action)

        colorspace_action = QtWidgets.QAction("Set Colorspace", ayon_menu)
        colorspace_action.triggered.connect(self.colorspace_callback)
        ayon_menu.addAction(colorspace_action)

        unit_scale_action = QtWidgets.QAction("Set Unit Scale", ayon_menu)
        unit_scale_action.triggered.connect(self.unit_scale_callback)
        ayon_menu.addAction(unit_scale_action)

        ayon_menu.addSeparator()
        template_builder = ayon_menu.addMenu("Template Builder")

        build_workfile_template_action = QtWidgets.QAction(
            "Build Workfile from Template", template_builder)
        build_workfile_template_action.triggered.connect(
            self.build_workfile_template_callback)
        template_builder.addAction(build_workfile_template_action)

        update_workfile_template_action = QtWidgets.QAction(
            "Update Workfile from Template", template_builder)
        update_workfile_template_action.triggered.connect(
            self.update_workfile_template_callback)
        template_builder.addAction(update_workfile_template_action)

        create_placeholders_action = QtWidgets.QAction(
            "Create Workfile Placeholders", template_builder)
        create_placeholders_action.triggered.connect(
            self.create_placeholders_callback)
        template_builder.addAction(create_placeholders_action)

        update_placeholders_action = QtWidgets.QAction(
            "Update Workfile Placeholders", template_builder)
        update_placeholders_action.triggered.connect(
            self.update_placeholders_callback)
        template_builder.addAction(update_placeholders_action)

        return ayon_menu

    def load_callback(self):
        """Callback to show Loader tool."""
        host_tools.show_loader(parent=self.main_widget)

    def publish_callback(self):
        """Callback to show Publisher tool."""
        host_tools.show_publisher(parent=self.main_widget)

    def manage_callback(self):
        """Callback to show Scene Manager/Inventory tool."""
        host_tools.show_scene_inventory(parent=self.main_widget)

    def library_callback(self):
        """Callback to show Library Loader tool."""
        host_tools.show_library_loader(parent=self.main_widget)

    def workfiles_callback(self):
        """Callback to show Workfiles tool."""
        host_tools.show_workfiles(parent=self.main_widget)

    def resolution_callback(self):
        """Callback to reset scene resolution"""
        return lib.reset_scene_resolution()

    def frame_range_callback(self):
        """Callback to reset frame range"""
        return lib.reset_frame_range()

    def colorspace_callback(self):
        """Callback to reset colorspace"""
        return lib.reset_colorspace()

    def unit_scale_callback(self):
        """Callback to reset unit scale"""
        return lib.validate_unit_scale()

    def version_up_callback(self):
        """Callback to version up current workfile."""
        return save_next_version()

    def build_workfile_template_callback(self):
        """Callback to build workfile from template."""
        build_workfile_template()

    def update_workfile_template_callback(self):
        """Callback to update workfile from template."""
        update_workfile_template()

    def create_placeholders_callback(self):
        """Callback to create workfile placeholders."""
        create_placeholder()

    def update_placeholders_callback(self):
        """Callback to update workfile placeholders."""
        update_placeholder()
