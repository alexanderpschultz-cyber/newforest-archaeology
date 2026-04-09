"""Generate patches from composite images for detailed analysis."""

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from config import PATCH_SIZE, PATCH_OVERLAP


@dataclass
class Patch:
    patch_id: str  # e.g. "415000_108000_r0_c0"
    tile_id: str
    row: int
    col: int
    x_offset: int  # pixel offset in composite
    y_offset: int
    width: int
    height: int
    image: Image.Image

    @property
    def x_frac(self) -> tuple[float, float]:
        """Fractional position in composite (0-1)."""
        return (self.x_offset / self.width, (self.x_offset + PATCH_SIZE) / self.width)

    @property
    def y_frac(self) -> tuple[float, float]:
        return (self.y_offset / self.height, (self.y_offset + PATCH_SIZE) / self.height)


def generate_patches(
    composite: Image.Image,
    tile_id: str,
    patch_size: int = PATCH_SIZE,
    overlap: int = PATCH_OVERLAP,
) -> list[Patch]:
    """Slice a composite image into overlapping patches."""
    w, h = composite.size
    stride = patch_size - overlap
    patches = []

    row = 0
    y = 0
    while y < h:
        col = 0
        x = 0
        while x < w:
            # Clamp to image bounds
            x2 = min(x + patch_size, w)
            y2 = min(y + patch_size, h)
            x1 = max(0, x2 - patch_size)
            y1 = max(0, y2 - patch_size)

            patch_img = composite.crop((x1, y1, x2, y2))
            patch = Patch(
                patch_id=f"{tile_id}_r{row}_c{col}",
                tile_id=tile_id,
                row=row,
                col=col,
                x_offset=x1,
                y_offset=y1,
                width=w,
                height=h,
                image=patch_img,
            )
            patches.append(patch)
            col += 1
            x += stride
            if x2 == w:
                break
        row += 1
        y += stride
        if y2 == h:
            break

    return patches
