# -*- coding: utf-8 -*-
"""Creator plugin for creating workfiles."""
import inspect
from ayon_core.pipeline import CreatedInstance, AutoCreator
from ayon_max.api import plugin
from ayon_max.api.lib import read, imprint
from pymxs import runtime as rt


class CreateWorkfile(plugin.MaxCreatorBase, AutoCreator):
    """Workfile auto-creator."""
    identifier = "io.ayon.creators.max.workfile"
    label = "Workfile"
    product_type = "workfile"
    product_base_type = "workfile"
    icon = "fa5.file"

    default_variant = "Main"

    settings_category = "max"

    def create(self):
        variant = self.default_variant
        current_instance = next(
            (
                instance for instance in self.create_context.instances
                if instance.creator_identifier == self.identifier
            ), None)

        project_entity = self.create_context.get_current_project_entity()
        folder_entity = self.create_context.get_current_folder_entity()
        task_entity = self.create_context.get_current_task_entity()

        project_name = project_entity["name"]
        folder_path = folder_entity["path"]
        task_name = task_entity["name"]
        host_name = self.create_context.host_name

        if current_instance is None:
            product_name = self.get_product_name(
                project_name=project_name,
                project_entity=project_entity,
                folder_entity=folder_entity,
                task_entity=task_entity,
                variant=variant,
                host_name=host_name,
            )
            data = {
                "folderPath": folder_path,
                "task": task_name,
                "variant": variant
            }

            data.update(
                self.get_dynamic_data(
                    project_name,
                    folder_entity,
                    task_entity,
                    variant,
                    host_name,
                    current_instance)
            )
            self.log.info("Auto-creating workfile instance...")
            instance_node = self.create_node(product_name)
            data["instance_node"] = instance_node.name
            current_instance = CreatedInstance(
                self.product_type, product_name, data, self
            )
            self._add_instance_to_context(current_instance)
            imprint(instance_node.name, current_instance.data)
        elif (
            current_instance["folderPath"] != folder_path
            or current_instance["task"] != task_name
        ):
            # Update instance context if is not the same
            product_name = self.get_product_name(
                project_name=project_name,
                project_entity=project_entity,
                folder_entity=folder_entity,
                task_entity=task_entity,
                variant=variant,
                host_name=host_name,
            )

            current_instance["folderPath"] = folder_entity["path"]
            current_instance["task"] = task_name
            current_instance["productName"] = product_name

    def collect_instances(self):
        self.cache_instance_data(self.collection_shared_data)
        cached_instances = self.collection_shared_data["max_cached_instances"]
        for instance in cached_instances.get(self.identifier, []):
            if not rt.getNodeByName(instance):
                continue
            created_instance = CreatedInstance.from_existing(
                read(rt.GetNodeByName(instance)), self
            )
            self._add_instance_to_context(created_instance)

    def update_instances(self, update_list):
        for created_inst, _ in update_list:
            instance_node = created_inst.get("instance_node")
            imprint(
                instance_node,
                created_inst.data_to_store()
            )

    def create_node(self, product_name):
        if rt.getNodeByName(product_name):
            node = rt.getNodeByName(product_name)
            return node
        node = rt.Container(name=product_name)
        node.isHidden = True
        return node
