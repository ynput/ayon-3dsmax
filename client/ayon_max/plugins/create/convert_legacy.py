# -*- coding: utf-8 -*-
"""Converter for legacy Max products."""
from ayon_core.pipeline.create.creator_plugins import ProductConvertorPlugin
from ayon_max.api.lib import imprint
try:
    from pymxs import runtime as rt

except ImportError:
    rt = None


class MaxLegacyConvertor(ProductConvertorPlugin):
    """Find and convert any legacy products in the scene.

    This Converter will find all legacy products in the scene and will
    transform them to the current system. Since the old products doesn't
    retain any information about their original creators, the only mapping
    we can do is based on their product types.

    Its limitation is that you can have multiple creators creating product
    of the same product type and there is no way to handle it. This code
    should nevertheless cover all creators that came with Ayon.

    """
    identifier = "io.ayon.creators.max.legacy"
    product_type_to_id = {
        "io.openpype.creators.max.camera": "io.ayon.creators.max.camera",
        "io.openpype.creators.max.maxScene": "io.ayon.creators.max.maxScene",
        "io.openpype.creators.max.model": "io.ayon.creators.max.model",
        "io.openpype.creators.max.pointcache": "io.ayon.creators.max.pointcache",
        "io.openpype.creators.max.pointcloud": "io.ayon.creators.max.pointcloud",
        "io.openpype.creators.max.redshiftproxy": "io.ayon.creators.max.redshiftproxy",
        "io.openpype.creators.max.maxrender": "io.ayon.creators.max.render",
        "io.openpype.creators.max.review": "io.ayon.creators.max.review",
        "io.openpype.creators.max.tyflow": "io.ayon.creators.max.tyflow",
        "io.openpype.creators.max.workfile": "io.ayon.creators.max.workfile",
    }

    def __init__(self, *args, **kwargs):
        super(MaxLegacyConvertor, self).__init__(*args, **kwargs)
        self.legacy_instances = {}

    def find_instances(self):
        """Find legacy products in the scene.

        Legacy products are the ones that doesn't have `creator_identifier`
        parameter on them.

        This is using cached entries done in
        :py:meth:`~MaxCreator.cache_instance_data()`

        """
        self.legacy_instances = self.collection_shared_data.get(
            "max_cached_legacy_instances")
        if not self.legacy_instances:
            return
        self.add_convertor_item(
            "Found {} incompatible product{}".format(
                len(self.legacy_instances),
                "s" if len(self.legacy_instances) > 1 else ""
            )
        )

    def convert(self):
        """Convert all legacy products to current.

        It is enough to add `creator_identifier` and `instance_node`.

        """
        if not self.legacy_instances:
            return

        for old_creator_id, instance_nodes in self.legacy_instances.items():
            if old_creator_id in self.product_type_to_id:
                for instance_node in instance_nodes:
                    new_creator_id = self.product_type_to_id[old_creator_id]
                    self.log.info(
                        "Converting {} to {}".format(instance_node,
                                                     new_creator_id)
                    )
                    imprint(instance_node, data={
                        "creator_identifier": new_creator_id
                    })
