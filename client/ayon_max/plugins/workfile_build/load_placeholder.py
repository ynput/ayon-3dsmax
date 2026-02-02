"""Placeholder to trigger loader action during workfile build."""
from __future__ import annotations
from pymxs import runtime as rt

from ayon_core.pipeline.workfile.workfile_template_builder import (
    PlaceholderLoadMixin,
    LoadPlaceholderItem
)

from ayon_max.api.pipeline import get_containers
from ayon_max.api.lib import read
from ayon_max.api.plugin import MS_CUSTOM_ATTRIB
from ayon_max.api.workfile_template_builder import (
    MaxPlaceholderPlugin,
)


class MaxPlaceholderLoadPlugin(MaxPlaceholderPlugin, PlaceholderLoadMixin):
    identifier = "max.load"
    label = "Max load"

    item_class = LoadPlaceholderItem

    def _create_placeholder_name(self, placeholder_data):

        # Split builder type: context_assets, linked_assets, all_assets
        prefix, suffix = placeholder_data["builder_type"].split("_", 1)
        parts = [prefix]

        placeholder_product_type = placeholder_data.get("product_type")
        if placeholder_product_type:
            parts.append(placeholder_product_type)

        # add loader arguments if any
        loader_args = placeholder_data["loader_args"]
        if loader_args:
            loader_args = eval(loader_args)
            for value in loader_args.values():
                parts.append(str(value))

        parts.append(suffix)
        placeholder_name = "_".join(parts)

        return placeholder_name.capitalize()

    def _get_loaded_repre_ids(self):
        loaded_representation_ids = self.builder.get_shared_populate_data(
            "loaded_representation_ids"
        )
        if loaded_representation_ids is None:
            try:
                containers = get_containers()

            except ValueError:
                containers = []

            container_data = {
                read(container)
                for container in containers
            }
            loaded_representation_ids = {
                data["representation"]
                for data in container_data
            }
            self.builder.set_shared_populate_data(
                "loaded_representation_ids", loaded_representation_ids
            )
        return loaded_representation_ids

    def populate_placeholder(self, placeholder):
        self.populate_load_placeholder(placeholder)
        if not placeholder.data.get("keep_placeholder", True):
            self.delete_placeholder(placeholder)

    def repopulate_placeholder(self, placeholder):
        repre_ids = self._get_loaded_repre_ids()
        self.populate_load_placeholder(placeholder, repre_ids)

    def get_placeholder_options(self, options=None):
        return self.get_load_plugin_options(options)

    def load_succeed(self, placeholder, container):
        self._parent_in_hierarchy(placeholder, container)

    def _parent_in_hierarchy(self, placeholder, container):
        """Parent loaded container to placeholder's parent.

        ie : Set loaded content as placeholder's sibling

        Args:
            container (str): Placeholder loaded container
        """

        if not container:
            return

        loaded_containers: list[rt.objects] = [
            target_container
            for target_container in get_containers()
            if container == target_container.name
        ]

        placeholder_node = rt.getNodeByName(placeholder.scene_identifier) or []
        if placeholder_node:
            loaded_containers_to_be_stored = []
            loaded_containers_name = []
            modifier = rt.EmptyModifier()
            rt.addModifier(placeholder_node, modifier)
            attrs = rt.Execute(MS_CUSTOM_ATTRIB)
            placeholder_node.modifiers[0].name = "AYON Placeholder Data"
            rt.custAttributes.add(placeholder_node.modifiers[0], attrs)
            # add the node reference of the loaded containers into
            # the placeholder container
            # all_handles attributes would store the node reference
            # sel_list attribute would store the name of the nodes
            # By this, we can keep a reference to the loaded containers,
            # as needed for update template from workfile.
            for i in loaded_containers:
                node_ref = rt.NodeTransformMonitor(node=i)
                loaded_containers_to_be_stored.append(node_ref)
                loaded_containers_name.append(str(i))
            rt.setProperty(
                placeholder_node.modifiers[0].AYONPlaceholderData,
                "all_handles", loaded_containers_to_be_stored)
            rt.setProperty(
                placeholder_node.modifiers[0].AYONPlaceholderData,
                "sel_list", loaded_containers_name)
