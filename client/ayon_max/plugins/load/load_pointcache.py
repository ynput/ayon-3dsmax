# -*- coding: utf-8 -*-
"""Simple alembic loader for 3dsmax.

Because of limited api, alembics can be only loaded, but not easily updated.

"""
import os
from ayon_core.pipeline import load
from ayon_max.api import lib, maintained_selection
from ayon_max.api.lib import unique_namespace, reset_frame_range
from ayon_max.api.pipeline import (
    containerise,
    get_previous_loaded_object,
    remove_container_data
)


class AbcLoader(load.LoaderPlugin):
    """Alembic loader."""

    product_types = {"camera", "animation", "pointcache"}
    label = "Load Alembic"
    representations = {"abc"}
    order = -10
    icon = "code-fork"
    color = "orange"

    def load(self, context, name=None, namespace=None, data=None):
        from pymxs import runtime as rt

        file_path = self.filepath_from_context(context)
        file_path = os.path.normpath(file_path)

        abc_before = {
            c
            for c in rt.rootNode.Children
            if rt.classOf(c) == rt.AlembicContainer
        }

        rt.AlembicImport.ImportToRoot = False
        # TODO: it will be removed after the improvement
        # on the post-system setup
        reset_frame_range()
        rt.importFile(file_path, rt.name("noPrompt"), using=rt.AlembicImport)

        abc_after = {
            c
            for c in rt.rootNode.Children
            if rt.classOf(c) == rt.AlembicContainer
        }

        # This should yield new AlembicContainer node
        abc_containers = abc_after.difference(abc_before)

        if len(abc_containers) != 1:
            self.log.error("Something failed when loading.")

        abc_container = abc_containers.pop()
        selections = rt.GetCurrentSelection()
        for abc in selections:
            for cam_shape in abc.Children:
                cam_shape.playbackType = 0

        namespace = unique_namespace(
            name + "_",
            suffix="_",
        )
        abc_objects = []
        for abc_object in abc_container.Children:
            abc_object.name = f"{namespace}:{abc_object.name}"
            abc_objects.append(abc_object)
        # rename the abc container with namespace
        abc_container_name = f"{namespace}:{name}"
        abc_container.name = abc_container_name
        abc_objects.append(abc_container)

        return containerise(
            name, abc_objects, context,
            namespace, loader=self.__class__.__name__
        )

    def update(self, container, context):
        from pymxs import runtime as rt

        repre_entity = context["representation"]
        path = os.path.normpath(self.filepath_from_context(context))
        node = rt.GetNodeByName(container["instance_node"])
        abc_container = [n for n in get_previous_loaded_object(node)
                         if rt.ClassOf(n) == rt.AlembicContainer]
        with maintained_selection():
            rt.Select(abc_container)

            for alembic in rt.Selection:
                abc = rt.GetNodeByName(alembic.name)
                rt.Select(abc.Children)
                for abc_con in abc.Children:
                    abc_con.source = path
                    rt.Select(abc_con.Children)
                    for abc_obj in abc_con.Children:
                        abc_obj.source = path

        lib.imprint(container["instance_node"], {
            "representation": repre_entity["id"],
            "project_name": context["project"]["name"]
        })

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        from pymxs import runtime as rt
        node = rt.GetNodeByName(container["instance_node"])
        remove_container_data(node)


    @staticmethod
    def get_container_children(parent, type_name):
        from pymxs import runtime as rt

        def list_children(node):
            children = []
            for c in node.Children:
                children.append(c)
                children += list_children(c)
            return children

        filtered = []
        for child in list_children(parent):
            class_type = str(rt.classOf(child.baseObject))
            if class_type == type_name:
                filtered.append(child)

        return filtered
