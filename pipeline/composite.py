"""Generate composite images from multiple LIDAR layers for a single tile."""

from pathlib import Path

import numpy as np
from PIL import Image

from pipeline.tile_loader import TileInfo, read_tile, normalize_to_uint8


# Preferred layer order for 2x2 composite
COMPOSITE_LAYERS = ["slope", "LRM", "multiHS", "openpos"]


def make_composite(tile: TileInfo, target_size: int = 1024) -> Image.Image | None:
    """Create a 2x2 composite image from available layers.

    Returns a PIL Image with four panels. If fewer than 4 layers are available,
    duplicates the available layers to fill the grid (better than blank panels
    which confuse the vision model).
    """
    available = []
    panel_size = target_size // 2

    for layer_name in COMPOSITE_LAYERS:
        if layer_name in tile.layers:
            data, meta = read_tile(tile.layers[layer_name])
            band = data[0]
            img_data = normalize_to_uint8(band, nodata=meta["nodata"])
            img = Image.fromarray(img_data, mode="L")
            img = img.resize((panel_size, panel_size), Image.LANCZOS)
            available.append(img)

    if not available:
        return None

    # Fill 4 slots by cycling available panels
    panels = [available[i % len(available)] for i in range(4)]

    # Assemble 2x2 grid
    composite = Image.new("L", (target_size, target_size))
    composite.paste(panels[0], (0, 0))
    composite.paste(panels[1], (panel_size, 0))
    composite.paste(panels[2], (0, panel_size))
    composite.paste(panels[3], (panel_size, panel_size))

    return composite


def save_composite(tile: TileInfo, output_dir: Path, target_size: int = 1024) -> Path | None:
    """Generate and save a composite image for a tile."""
    output_dir.mkdir(parents=True, exist_ok=True)
    composite = make_composite(tile, target_size)
    if composite is None:
        return None
    out_path = output_dir / f"{tile.tile_id}_composite.png"
    composite.save(out_path)
    return out_path
