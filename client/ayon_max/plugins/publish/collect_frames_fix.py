import pyblish.api
import ayon_api

from ayon_core.lib import TextDef, BoolDef
from ayon_core.pipeline.publish import AYONPyblishPluginMixin



class CollectFramesFixDefMax(pyblish.api.InstancePlugin,
                             AYONPyblishPluginMixin):
    """Provides text field to insert frame(s) to be re-rendered.

    Published files of last version of an instance product are collected into
    `instance.data["last_version_published_files"]`. All these but frames
    mentioned in text field will be reused for new version.
    """
    order = pyblish.api.CollectorOrder + 0.495
    label = "Collect Frames to Fix"
    hosts = ["max"]
    targets = ["local"]
    families = ["maxrender"]
    settings_category = "max"

    rewrite_version = False

    def process(self, instance):
        attribute_values = self.get_attr_values_from_data(instance.data)
        frames_to_fix: str = attribute_values.get("frames_to_fix", "")
        rewrite_version: bool = (
            self.rewrite_version
            and attribute_values.get("rewrite_version", False)
        )
        if not frames_to_fix:
            if rewrite_version:
                self.log.warning(
                    "Rewrite version is enabled but no frames to fix are "
                    "specified. Rewriting last version will be skipped.")
            return

        self.log.info(f"Frames to fix: {frames_to_fix}")
        instance.data["frames_to_fix"] = frames_to_fix

        folder_entity: dict = instance.data["folderEntity"]
        project_entity: dict = instance.data["projectEntity"]
        project_name: str = project_entity["name"]

        # NOTE: This instance only triggers the render and it has `integrate`
        # disabled by `CollectLocalRenderInstances`. The products which are
        # published are the render instances spawned from it, so the previous
        # version has to be resolved for each of them separately.
        reused_files: "list[str]" = []
        for render_instance in instance.context:
            if render_instance is instance:
                continue

            render_families = set(render_instance.data.get("families") or [])
            if "render.local" not in render_families:
                continue
            if not render_instance.data.get("integrate", True):
                continue
            if (
                render_instance.data.get("instance_node")
                != instance.data.get("instance_node")
            ):
                continue

            product_name: str = render_instance.data.get("productName") or ""
            product_entity = ayon_api.get_product_by_name(
                project_name,
                product_name,
                folder_id=folder_entity["id"])
            if not product_entity:
                self.log.warning(
                    f"No existing product found for '{product_name}'. "
                    "Re-render not possible."
                )
                continue

            product_base_type = (
                    product_entity["productBaseType"]
                    or product_entity["productType"]
            )
            instance_product_base_type = render_instance.data.get(
                "productBaseType")
            if (
                instance_product_base_type
                and product_base_type != instance_product_base_type
            ):
                self.log.error(
                    f"Existing product '{product_name}' product base type "
                    f"'{product_base_type}' is not the same as instance "
                    "product base type "
                    f"'{instance_product_base_type}'. Re-render may have "
                    "unintended side effects.")

            version_entity = ayon_api.get_last_version_by_product_id(
                project_name,
                product_id=product_entity["id"],
            )
            if not version_entity:
                self.log.warning(
                    f"No last version found for product '{product_name}', "
                    "re-render not possible."
                )
                continue

            # Get all published files for the representation of this product
            published_files: "list[str]" = []
            representations = ayon_api.get_representations(
                project_name, version_ids={version_entity["id"]}
            )
            for repre in representations:
                for file_info in repre.get("files"):
                    published_files.append(file_info["path"])

            if not published_files:
                self.log.debug(
                    f"No published files found for '{product_name}'."
                )
                continue

            self.log.debug(
                f"last_version_published_files of '{product_name}': "
                f"{published_files}"
            )
            render_instance.data["frames_to_fix"] = frames_to_fix
            render_instance.data["last_version_published_files"] = (
                published_files
            )
            reused_files.extend(published_files)

            if rewrite_version:
                render_instance.data["version"] = version_entity["version"]
                # limits triggering version validator
                render_instance.data.pop("latestVersion", None)

        # The trigger instance does not publish a product itself, but the local
        # render is only limited to the frames to fix when a previous version
        # is available, so keep that signal on it as well.
        instance.data["last_version_published_files"] = reused_files

    @classmethod
    def get_attribute_defs(cls):
        attributes = [
            TextDef("frames_to_fix", label="Frames to fix",
                    placeholder="5,10-15",
                    regex="[0-9,-]+",
                    tooltip=(
                        "When specified, only these frames will be rendered.\n"
                        "The remainder of the frame range for the instance "
                        "will be copied from the previous published version.\n"
                        "This allows re-rendering only certain frames or "
                        "extending the frame range of the previous version.\n"
                        "The frames to fix must be inside the instance's "
                        "frame range.\n"
                        "Example: 5,10-15"
                    ))
        ]

        if cls.rewrite_version:
            attributes.append(
                BoolDef(
                    "rewrite_version",
                    label="Rewrite latest version",
                    default=False,
                    tooltip=(
                        "When enabled the new version will be published into"
                        "the previous version and apply only the 'fixed "
                        "frames'.\n"
                        "**Note:** This does nothing if no Frames to Fix are "
                        "specified."
                    )
                )
            )

        return attributes
