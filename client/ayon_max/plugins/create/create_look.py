# -*- coding: utf-8 -*-
"""Creator plugin for creating camera."""
import os
from pathlib import Path

from ayon_core.pipeline import CreatorError
from ayon_max.api.plugin import MaxCreator

from pymxs import runtime as rt


class CreateLook(MaxCreator):
    """Creator plugin for Material Library."""
    identifier = "io.ayon.creators.max.look"
    label = "Look"
    product_base_type = "look"
    product_type = product_base_type
    icon = "gear"

    # Settings
    remove_matlib_when_remove_instance = True

    def create(self, product_name, instance_data, pre_create_data):
        """Create a new look instance which stores material library.

        Args:
            product_name (str): Name of the product.
            instance_data (dict): Data related to the instance.
            pre_create_data (dict): Data related to the pre-creation process.

        Raises:
            CreatorError: If a look instance already exists.
        """
        # I need to create dummy mat instance and then open it
        # imprint matlib_filepath as part of the data
        matlib_filepath = self.get_material_library_filepath(
            instance_data, product_name
        )
        instance_data["matlib_filepath"] = matlib_filepath
        container = rt.getNodeByName(product_name)
        product_base_type = instance_data["productBaseType"]
        # check if there is existing look instance
        if container and product_name.startswith(product_base_type):
            raise CreatorError("Look instance already exists")

        super(CreateLook, self).create(
            product_name,
            instance_data,
            pre_create_data)

        # open material library
        rt.sme.OpenMtlLib(matlib_filepath)

    def remove_instances(self, instances):
        """Remove specified instance from the scene.

        Remove the instance node and close the material library
        associated with the instance.

        """
        for instance in instances:
            instance_node = rt.GetNodeByName(
                instance.data.get("instance_node"))

            # close material library if exists and remove it
            material_library_filepath = instance.data.get("matlib_filepath")
            rt.sme.CloseMtlLib(material_library_filepath)

            if self.remove_matlib_when_remove_instance:
                os.remove(material_library_filepath)

            if instance_node:
                rt.Delete(instance_node)

            self._remove_instance_from_context(instance)

    def get_material_library_filepath(self, instance_data, product_name):
        """Get the file path for the material library.

        Args:
            instance_data (dict): Data related to the instance.
            product_name (str): Name of the product.

        Returns:
            str: File path for the material library.
        """
        workdir = os.getenv("AYON_WORKDIR")
        # TODO: support to customize matlib folder template in the settings
        folder_path = instance_data["folderPath"]
        task = instance_data["task"]
        matlib_directory = Path(workdir) / "matlib" / folder_path / task
        matlib_directory.mkdir(parents=True, exist_ok=True)
        matlib_filepath = matlib_directory / f"{product_name}.mat"
        # If the file exists, uses the existing one,
        # otherwise creates a new one.
        if not matlib_filepath.exists():
            with open(matlib_filepath, "w", encoding="utf-8") as f: pass

        return str(matlib_filepath)

    def get_pre_create_attr_defs(self):
        return []
