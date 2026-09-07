from ayon_max.api.plugin import TestCreator


class TestCreate(TestCreator):
    """Test Creator."""
    identifier = "Test"
    label = "test"
    product_base_type = "test"
    product_type = product_base_type
    icon = "gear"