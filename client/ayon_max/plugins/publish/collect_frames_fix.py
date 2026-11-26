from __future__ import annotations

import os
import re
from dataclasses import dataclass

import clique
import pyblish.api
import ayon_api

from ayon_core.lib import TextDef, BoolDef, collect_frames
from ayon_core.pipeline.publish import (
    AYONPyblishPluginMixin,
    PublishError,
)

# Frame number at the end of a file name, e.g. `beauty.1001.exr`
FRAME_IN_FILE_NAME = re.compile(r"\.(?P<frame>[0-9]+)(?:\.[^.]+)?$")


def _frame_from_file_name(file_name):
    """Get the frame number of a rendered file name, None when it has none."""
    match = FRAME_IN_FILE_NAME.search(os.path.basename(file_name))
    if not match:
        return None
    return int(match.group("frame"))


def _representation_files(representation):
    """Get the file names of a representation as a list."""
    files = representation.get("files") or []
    return [files] if isinstance(files, str) else files


@dataclass
class PreviousVersion:
    """Previous published version of a render product."""

    product: dict
    version: dict
    published_files: list[str]


class CollectFramesFixDefMax(pyblish.api.InstancePlugin,
                             AYONPyblishPluginMixin):
    """Collect the frames to fix and the previous version to copy from.

    `frames_to_fix` renders only the given frames, the remaining frames are
    copied from the previous published version by `ExtractLastPublished`.
    Frames which cannot be copied (no product/version, no file, changed image
    format) are rendered too, otherwise they would be missing in the version.
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
        frames_to_fix = attribute_values.get("frames_to_fix", "")
        rewrite_version = bool(
            self.rewrite_version
            and attribute_values.get("rewrite_version", False)
        )
        if not frames_to_fix:
            if rewrite_version:
                self.log.warning(
                    "Rewrite version is enabled but no frames to fix are "
                    "specified. Rewriting last version will be skipped.")
            return

        self.log.info("Frames to fix: %s", frames_to_fix)
        instance.data["frames_to_fix"] = frames_to_fix
        # The frames which are not re-rendered are copied to the frame numbers
        # they had in the previous version, so the published version must not
        # renumber them to consecutive frames.
        instance.data["hasExplicitFrames"] = True
        # The validators need to know whether the last version is rewritten,
        # the attribute itself is stored in the publish attributes.
        instance.data["rewrite_version"] = rewrite_version

        expected_frames = set(instance.data.get("expectedFrameRange") or [])
        if not expected_frames:
            self.log.debug(
                "No expected frame range collected, skipping frames to fix.")
            return

        fix_frames = self._parse_frames_to_fix(frames_to_fix)
        reuse_frames = expected_frames - fix_frames
        frames_to_render = fix_frames & expected_frames

        project_name = instance.data["projectEntity"]["name"]
        folder_id = instance.data["folderEntity"]["id"]
        anatomy = instance.context.data.get("anatomy")

        # A local render publishes one product per AOV through spawned
        # `render.local` instances, so the previous version is resolved for
        # each of them. A farm render has no spawned instances, its products
        # are created by the farm publish job (see `_get_farm_frames`).
        render_instances = self._get_local_render_instances(instance)
        previous_versions = self._get_previous_versions(
            project_name,
            folder_id,
            [render_instance.data.get("productName")
             for render_instance in render_instances],
        )
        copies = []
        for render_instance in render_instances:
            product_name = render_instance.data.get("productName")
            published_files, reusable_frames, reason = self._get_reusable_files(
                render_instance, previous_versions.get(product_name), anatomy)
            if reason:
                self.log.warning(
                    f"Cannot reuse the frames of '{product_name}': {reason} "
                    "The frames are rendered instead.")
                frames_to_render |= reuse_frames
                continue

            not_reusable_frames = reuse_frames - reusable_frames
            if not_reusable_frames:
                self.log.warning(
                    f"These frames cannot be reused from the previous version "
                    f"of '{product_name}' and are rendered too: "
                    f"{sorted(not_reusable_frames)}")
                frames_to_render |= not_reusable_frames

            copies.append(
                (render_instance, previous_versions[product_name],
                 published_files, reusable_frames))

        publish_instances = []
        previous_versions = {}

        if instance.data.get("farm"):
            (
                farm_frames,
                publish_instances,
                previous_versions,
            ) = self._get_farm_frames(
                instance, project_name, folder_id, anatomy, reuse_frames)
            frames_to_render |= farm_frames

        frames_to_render = sorted(frames_to_render)
        self.log.info(
            "Frames to fix: %s, frames to render: %s",
            frames_to_fix, frames_to_render)
        # Both local render paths, `ExtractLocalRender` and the multi camera
        # batch script, render exactly these frames.
        instance.data["frames_to_render"] = frames_to_render

        if publish_instances:
            self._collect_reused_files(
                instance, publish_instances, previous_versions,
                frames_to_render, anatomy)

        if rewrite_version:
            self._rewrite_farm_version(instance, project_name, folder_id)

        for render_instance, previous, published_files, reusable in copies:
            if rewrite_version:
                render_instance.data["version"] = previous.version["version"]
                # limits triggering version validator
                render_instance.data.pop("latestVersion", None)

            # Only the frames which are not rendered have to be copied.
            if not reusable.difference(frames_to_render):
                continue

            render_instance.data["frames_to_fix"] = frames_to_fix
            render_instance.data["frames_to_render"] = frames_to_render
            render_instance.data["last_version_published_files"] = (
                published_files)

    def _get_farm_frames(
            self, instance, project_name, folder_id, anatomy, reuse_frames):
        """Frames of a farm render which cannot be copied from the previous one.

        A farm instance is integrated by the farm publish job, so its products
        are resolved the same way the publish job does them (see
        `_get_publish_instances`).

        Returns:
            tuple: Frames which have to be rendered, the instances the farm
                publish job creates and their previous versions.

        """
        if not reuse_frames:
            # Every frame is rendered, there is nothing to copy.
            return set(), [], {}

        publish_instances = self._get_publish_instances(instance)
        if not publish_instances:
            self.log.warning(
                "No product found which the farm publish job would create for "
                "the instance. The frames are rendered instead.")
            return set(reuse_frames), [], {}

        product_names = [
            publish_instance["productName"]
            for publish_instance in publish_instances
            if publish_instance.get("productName")
        ]
        previous_versions = self._get_previous_versions(
            project_name, folder_id, product_names)

        frames_to_render = set()
        for product_name in product_names:
            _files, reusable_frames, reason = self._get_reusable_files(
                instance, previous_versions.get(product_name), anatomy,
                compare_base_type=False)
            if reason:
                self.log.warning(
                    f"Cannot reuse the frames of '{product_name}': {reason} "
                    "The frames are rendered instead.")
                return set(reuse_frames), publish_instances, previous_versions

            not_reusable_frames = set(reuse_frames) - reusable_frames
            if not_reusable_frames:
                self.log.warning(
                    f"These frames cannot be reused from the previous version "
                    f"of '{product_name}' and are rendered too: "
                    f"{sorted(not_reusable_frames)}")
            frames_to_render |= not_reusable_frames

        return frames_to_render, publish_instances, previous_versions

    def _collect_reused_files(
            self, instance, publish_instances, previous_versions,
            frames_to_render, anatomy):
        """Collect the files of the reused frames the publish job needs.

        The farm publish job lists every frame of the version in its
        representations. When the Deadline publish job waits for the rendered
        files (the addon setting `Add rendered files as Dependencies`), the
        frames which are not rendered have to exist before the job starts,
        otherwise it waits forever for files the render job never writes.
        `PrepareFrameFixDependencies` copies the collected files right before
        the job is submitted.
        """
        rendered = {int(frame) for frame in frames_to_render}
        copies = []
        seen = set()
        for publish_instance in publish_instances:
            product_name = publish_instance.get("productName")
            previous = previous_versions.get(product_name)
            if not previous:
                continue

            sources_by_frame = {
                int(frame): path
                for path, frame in collect_frames(
                    previous.published_files).items()
                if frame is not None
            }
            for representation in (
                    publish_instance.get("representations") or []):
                staging_dir = representation.get("stagingDir") or ""
                if staging_dir.startswith("{") and anatomy is not None:
                    staging_dir = anatomy.fill_root(staging_dir)
                for file_name in _representation_files(representation):
                    frame = _frame_from_file_name(file_name)
                    if frame is None or frame in rendered:
                        continue
                    source = sources_by_frame.get(frame)
                    if not source:
                        self.log.warning(
                            "The reused frame %s of '%s' has no file in the "
                            "previous version.", frame, product_name)
                        continue
                    target = os.path.join(staging_dir, file_name)
                    key = os.path.normpath(target)
                    if key in seen:
                        continue
                    seen.add(key)
                    if anatomy is not None:
                        source = anatomy.fill_root(source)
                    copies.append((source, target))

        if copies:
            instance.data["frame_fix_reused_files"] = copies
            self.log.debug(
                "Reused frames which the Deadline publish job needs: %s",
                len(copies))
        return copies

    def _get_publish_instances(self, instance):
        """Get the instances the farm publish job creates.

        `instance.data["productName"]` of a farm render instance is the name of
        the render instance (`maxrenderMain`), not of the published product
        (`renderLookdevMain_Beauty`). The publish job creates the products with
        `create_instances_for_aov`, whose naming has to be used here as well.
        """
        from ayon_core.pipeline.farm.pyblish_functions import (
            create_skeleton_instance,
            create_instances_for_aov,
        )

        try:
            # Mirrors `CollectLocalRenderInstances` / `SubmitPublishJob`, so
            # the names are exactly the ones of the farm publish instances.
            skeleton = create_skeleton_instance(
                instance,
                families_transfer=[],
                instance_transfer={},
            )
            publish_instances = create_instances_for_aov(
                instance=instance,
                skeleton=skeleton,
                aov_filter={"max": [r".*"]},
                skip_integration_repre_list=[],
                do_not_add_review=False,
            )
        except Exception as exc:
            self.log.warning(
                "Could not resolve the products which the farm publish job "
                f"creates ({type(exc).__name__}: {exc}), falling back to the "
                "collected product name.")
            product_name = instance.data.get("productName")
            return [{"productName": product_name}] if product_name else []

        product_names = [
            publish_instance["productName"]
            for publish_instance in publish_instances
            if publish_instance.get("productName")
        ]
        self.log.debug(
            "Products created by the farm publish job: %s", product_names)
        return publish_instances

    def _get_previous_versions(self, project_name, folder_id, product_names):
        """Get the previous published version of the products.

        Three queries are used for any number of products, products without a
        last version are missing from the result.
        """
        product_names = {name for name in product_names if name}
        if not product_names:
            return {}

        products_by_name = {
            product["name"]: product
            for product in ayon_api.get_products(
                project_name,
                product_names=product_names,
                folder_ids={folder_id},
                fields={"id", "name", "productBaseType", "productType"},
            )
        }
        last_versions = ayon_api.get_last_versions(
            project_name,
            [product["id"] for product in products_by_name.values()],
            fields={"id", "version"},
        )

        published_files_by_version = {}
        for representation in ayon_api.get_representations(
                project_name,
                version_ids={
                    version["id"] for version in last_versions.values()
                    if version}):
            version_id = representation.get("versionId")
            if not version_id:
                continue
            published_files = published_files_by_version.setdefault(
                version_id, [])
            for file_info in representation.get("files") or []:
                published_files.append(file_info["path"])

        previous_versions = {}
        for product_name, product in products_by_name.items():
            version_entity = last_versions.get(product["id"])
            if not version_entity:
                continue
            previous_versions[product_name] = PreviousVersion(
                product=product,
                version=version_entity,
                published_files=published_files_by_version.get(
                    version_entity["id"], []),
            )
        return previous_versions

    def _get_reusable_files(
            self, instance, previous, anatomy, compare_base_type=True):
        """Get the files and frames of the previous version which can be used.

        Returns the published files, the reusable frames and the reason why the
        previous version cannot be used at all (`None` when it can be used).
        The base type is only compared for the local render instances, a farm
        instance publishes with the base type of the host.
        """
        if not previous:
            return None, None, "no published product or last version."
        if compare_base_type:
            mismatch = self._get_product_mismatch(previous, instance)
            if mismatch:
                return None, None, mismatch

        # The output format may have changed since the previous version, only
        # files of the current representations can be reused.
        current_extensions = set()
        for representation in instance.data.get("representations") or []:
            for file_name in _representation_files(representation):
                extension = os.path.splitext(file_name)[1].lower()
                if extension:
                    current_extensions.add(extension)
        published_files = [
            file_path for file_path in previous.published_files
            if not current_extensions
            or os.path.splitext(file_path)[1].lower() in current_extensions
        ]
        if not published_files:
            return None, None, "no published files of the current format."

        reusable_frames = set()
        for file_path, frame in collect_frames(published_files).items():
            if frame is None:
                continue
            if anatomy is not None and not os.path.exists(
                    anatomy.fill_root(file_path)):
                continue
            reusable_frames.add(int(frame))

        return published_files, reusable_frames, None

    @staticmethod
    def _get_product_mismatch(previous, instance):
        """Get the reason why the instance cannot publish into the product."""
        product_base_type = (
            previous.product.get("productBaseType")
            or previous.product.get("productType"))
        instance_base_type = instance.data.get("productBaseType")
        if (instance_base_type and product_base_type
                and product_base_type != instance_base_type):
            return (
                f"the product base type '{product_base_type}' does not match "
                f"the instance base type '{instance_base_type}'.")
        return None

    def _rewrite_farm_version(self, instance, project_name, folder_id):
        """Publish the farm job into the latest version instead of a new one."""
        # The rewrite has to happen in the collector: `ValidateVersion` rejects
        # publishing into an existing version while `latestVersion` is present.
        if not instance.data.get("farm") or instance.data.get("version"):
            return

        product_name = instance.data.get("productName")
        previous = self._get_previous_versions(
            project_name, folder_id, [product_name]).get(product_name)
        if not previous:
            self.log.warning(
                "Rewrite latest version is enabled but no previous version "
                "exists, a new version is published.")
            return

        instance.data["version"] = previous.version["version"]
        instance.data.pop("latestVersion", None)
        self.log.info(
            "Rewrite latest version: publishing into version %s",
            previous.version["version"])

    @staticmethod
    def _parse_frames_to_fix(frames_to_fix):
        """Parse the frames to fix value into frame numbers."""
        try:
            fix_frames = set(clique.parse(frames_to_fix, "{ranges}").indexes)
        except ValueError as exc:
            raise PublishError(
                f"Invalid frames to fix value '{frames_to_fix}': {exc}. "
                "Use a value like '1-10' or '1,3,5-12'."
            ) from exc

        if not fix_frames:
            raise PublishError(
                f"Frames to fix '{frames_to_fix}' does not contain any frame.")
        return fix_frames

    @staticmethod
    def _get_local_render_instances(instance):
        """Get the spawned, integrated `render.local` instances."""
        render_instances = []
        for render_instance in instance.context:
            if render_instance is instance:
                continue
            families = set(render_instance.data.get("families") or [])
            if "render.local" not in families:
                continue
            if not render_instance.data.get("integrate", True):
                continue
            if (render_instance.data.get("instance_node")
                    != instance.data.get("instance_node")):
                continue
            render_instances.append(render_instance)
        return render_instances

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
