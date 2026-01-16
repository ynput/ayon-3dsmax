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
        "camera": "io.ayon.creators.max.camera",
        "maxScene": "io.ayon.creators.max.maxScene",
        "model": "io.ayon.creators.max.model",
        "pointcache": "io.ayon.creators.max.pointcache",
        "pointcloud": "io.ayon.creators.max.pointcloud",
        "redshiftproxy": "io.ayon.creators.max.redshiftproxy",
        "maxrender": "io.ayon.creators.max.render",
        "review": "io.ayon.creators.max.review",
        "tyflow": "io.ayon.creators.max.tyflow",
        "workfile": "io.ayon.creators.max.workfile",
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

        for product_type, instance_nodes in self.legacy_instances.items():
            if product_type in self.product_type_to_id:
                for instance_node in instance_nodes:
                    creator_identifier = self.product_type_to_id[product_type]
                    self.log.info(
                        "Converting {} to {}".format(instance_node,
                                                     creator_identifier)
                    )
                    imprint(instance_node, data={
                        "creator_identifier": creator_identifier
                    })
