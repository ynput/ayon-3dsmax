"""Creator plugin for creating material library."""
import os

from ayon_core.pipeline import CreatorError
from ayon_max.api.plugin import MaxCreator

from pymxs import runtime as rt


class CreateMatlib(MaxCreator):
    """Creator plugin for Material Library."""
    identifier = "io.ayon.creators.max.matlib"
    label = "Material Library"
    product_base_type = "matlib"
    product_type = product_base_type
    icon = "gear"

    # Settings
    remove_matlib_when_remove_instance = True

    def create(self, product_name, instance_data, pre_create_data):
        """Create a new material library instance.

        Args:
            product_name (str): Name of the product.
            instance_data (dict): Data related to the instance.
            pre_create_data (dict): Data related to the pre-creation process.

        Raises:
            CreatorError: If a look instance already exists.
        """
        # I need to create dummy mat instance and then open it
        # imprint matlib_filepath as part of the data
        matlib_filepath = self.get_material_library_filepath(product_name)
        instance_data["matlib_filepath"] = matlib_filepath
        container = rt.getNodeByName(product_name)
        product_base_type = instance_data["productBaseType"]
        # check if there is existing material library instance
        if container and product_name.startswith(product_base_type):
            raise CreatorError("Material library instance already exists")

        super(CreateMatlib, self).create(
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

            if (
                self.remove_matlib_when_remove_instance
                and os.path.exists(material_library_filepath)
            ):
                self.log.warning(
                    f"Removing material library file: {material_library_filepath}"
                )
                os.remove(material_library_filepath)
                
                # Remove the parent directory if it is empty
                matlib_dir = os.path.dirname(material_library_filepath)
                if os.path.exists(matlib_dir) and not os.listdir(matlib_dir):
                    self.log.warning(
                        f"Removing empty material library directory: {matlib_dir}"
                    )
                    os.rmdir(matlib_dir)

            if instance_node:
                rt.Delete(instance_node)

            self._remove_instance_from_context(instance)

    def get_material_library_filepath(self, product_name):
        """Get the file path for the material library.

        Args:
            product_name (str): Name of the product.

        Returns:
            str: File path for the material library.
        """
        matlib_directory = os.path.join(os.getenv("AYON_WORKDIR"), "matlib")
        os.makedirs(matlib_directory, exist_ok=True)
        matlib_filepath = os.path.join(matlib_directory, f"{product_name}.mat")
        # If the file exists, uses the existing one,
        # otherwise creates a new one.
        if not os.path.exists(matlib_filepath):
            with open(matlib_filepath, "w", encoding="utf-8"):
                pass

        return matlib_filepath

    def get_pre_create_attr_defs(self):
        return []
