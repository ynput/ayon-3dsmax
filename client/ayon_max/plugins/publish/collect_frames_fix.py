import os

import clique
import pyblish.api
import ayon_api

from ayon_core.lib import TextDef, BoolDef, collect_frames
from ayon_core.pipeline.publish import (
    AYONPyblishPluginMixin,
    PublishError,
)


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

        # The frames which are not re-rendered have to be copied from the
        # previous published version. Any frame which cannot be copied has to be
        # rendered as well, otherwise it would be missing in the new version.
        expected_frames = set(instance.data.get("expectedFrameRange") or [])
        if not expected_frames:
            self.log.debug(
                "No expected frame range collected, skipping frames to fix."
            )
            return

        try:
            fix_frames = set(clique.parse(frames_to_fix, "{ranges}").indexes)
        except ValueError as exc:
            raise PublishError(
                f"Invalid frames to fix value '{frames_to_fix}': {exc}. "
                "Use a value like '1-10' or '1,3,5-12'."
            ) from exc

        if not fix_frames:
            raise PublishError(
                f"Frames to fix '{frames_to_fix}' does not contain any frame."
            )

        reuse_frames = expected_frames - fix_frames
        frames_to_render = fix_frames & expected_frames

        folder_entity: dict = instance.data["folderEntity"]
        project_entity: dict = instance.data["projectEntity"]
        project_name: str = project_entity["name"]
        anatomy = instance.context.data.get("anatomy")

        # NOTE: This instance only triggers the render and it has `integrate`
        # disabled by `CollectLocalRenderInstances`. The products which are
        # published are the render instances spawned from it, so the previous
        # version has to be resolved for each of them separately.
        candidates: "list[tuple]" = []
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
                    "Re-render not possible, the frames are rendered instead."
                )
                frames_to_render |= reuse_frames
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
                    "re-render not possible, the frames are rendered instead."
                )
                frames_to_render |= reuse_frames
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
                self.log.warning(
                    f"No published files found for '{product_name}', "
                    "re-render not possible, the frames are rendered instead."
                )
                frames_to_render |= reuse_frames
                continue

            reusable_frames = self._get_reusable_frames(
                published_files, anatomy)
            not_reusable_frames = reuse_frames - reusable_frames
            if not_reusable_frames:
                self.log.warning(
                    f"These frames cannot be reused from the previous version "
                    f"of '{product_name}' and are rendered too: "
                    f"{sorted(not_reusable_frames)}"
                )
                frames_to_render |= not_reusable_frames

            self.log.debug(
                f"last_version_published_files of '{product_name}': "
                f"{published_files}"
            )
            candidates.append((
                render_instance, version_entity, published_files,
                reusable_frames
            ))

        frames_to_render = sorted(frames_to_render)
        self.log.info(
            "Frames to fix: %s, frames to render: %s",
            frames_to_fix, frames_to_render
        )
        # Both local render paths, `ExtractLocalRender` and the multi camera
        # batch script, render exactly these frames.
        instance.data["frames_to_render"] = frames_to_render

        for render_instance, version_entity, published_files, reusable in (
            candidates
        ):
            if rewrite_version:
                render_instance.data["version"] = version_entity["version"]
                # limits triggering version validator
                render_instance.data.pop("latestVersion", None)

            # Only the frames which are not rendered have to be copied.
            if not reusable.difference(frames_to_render):
                continue

            render_instance.data["frames_to_fix"] = frames_to_fix
            render_instance.data["frames_to_render"] = frames_to_render
            render_instance.data["last_version_published_files"] = (
                published_files
            )

    @staticmethod
    def _get_reusable_frames(published_files, anatomy):
        """Get the frames of a previous version which can really be copied.

        Args:
            published_files (list[str]): Files of the previous version.
            anatomy (Anatomy): Anatomy used to resolve the root of the paths.

        Returns:
            set[int]: Frames whose file exists and can be copied.

        """
        reusable_frames: "set[int]" = set()
        for file_path, frame in collect_frames(published_files).items():
            if frame is None:
                continue
            if anatomy is not None and not os.path.exists(
                anatomy.fill_root(file_path)
            ):
                continue
            reusable_frames.add(int(frame))

        return reusable_frames

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
