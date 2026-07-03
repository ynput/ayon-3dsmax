import attr


try:
    from pymxs import runtime as rt

except ImportError:
    rt = None


@attr.s
class RenderProduct(object):
    """Getting Colorspace as
    Specific Render Product Parameter for submitting
    publish job.
    """
    productName = attr.ib(default="")
    colorspace = attr.ib(default="sRGB")
    view = attr.ib(default="ACES 1.0")
    display = attr.ib(default="sRGB")


@attr.s
class LayerMetadata(object):
    """Data class for Render Layer metadata."""
    frameStart = attr.ib()
    frameEnd = attr.ib()
    products: list[RenderProduct] = attr.ib(factory=list)


class ARenderProduct(object):

    def __init__(self, frame_start, frame_end):
        """Constructor."""
        # Initialize
        self.layer_data = self._get_layer_data(frame_start, frame_end)

    def _get_layer_data(
        self,
        frame_start: int,
        frame_end: int
    ) -> LayerMetadata:
        return LayerMetadata(
            frameStart=int(frame_start),
            frameEnd=int(frame_end),
        )


    def add_colorspace_data(
        self,
        product_name: str,
        colorspace: str,
        view: str,
        display: str
    ) -> None:
        """Add colorspace data to the render product.

        Args:
            product_name (str): The name of the render product.
            colorspace (str): The colorspace of the render product.
            view (str): The view of the render product.
            display (str): The display of the render product.
        """
        self.layer_data.products.append(RenderProduct(
            productName=product_name,
            colorspace=colorspace,
            view=view,
            display=display
        ))
