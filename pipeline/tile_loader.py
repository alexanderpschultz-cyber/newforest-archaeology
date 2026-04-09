"""Load and inspect LIDAR GeoTIFF tiles."""

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import rasterio

from config import DATA_DIR, LAYERS, LAYER_SUFFIXES


@dataclass
class TileInfo:
    tile_id: str  # e.g. "415000_108000"
    easting: int
    northing: int
    layers: dict[str, Path] = field(default_factory=dict)

    @property
    def available_layers(self) -> list[str]:
        return list(self.layers.keys())


def discover_tiles() -> dict[str, TileInfo]:
    """Scan the data directory and build a registry of all tiles and their layers."""
    tiles: dict[str, TileInfo] = {}
    tile_pattern = re.compile(r"^(\d{6})_(\d{5,6})")

    for layer_name, layer_dir in LAYERS.items():
        if not layer_dir.exists():
            continue
        suffix = LAYER_SUFFIXES[layer_name]
        for tif_path in sorted(layer_dir.glob("*.tif")):
            # Extract tile_id from filename
            fname = tif_path.stem
            if suffix:
                fname = fname.replace(suffix, "")
            m = tile_pattern.match(fname)
            if not m:
                continue
            tile_id = f"{m.group(1)}_{m.group(2)}"
            easting, northing = int(m.group(1)), int(m.group(2))

            if tile_id not in tiles:
                tiles[tile_id] = TileInfo(
                    tile_id=tile_id, easting=easting, northing=northing
                )
            tiles[tile_id].layers[layer_name] = tif_path

    return tiles


def read_tile(path: Path) -> tuple[np.ndarray, dict]:
    """Read a GeoTIFF and return (data_array, metadata_dict)."""
    with rasterio.open(path) as src:
        data = src.read()  # shape: (bands, height, width)
        meta = {
            "crs": src.crs,
            "transform": src.transform,
            "bounds": src.bounds,
            "width": src.width,
            "height": src.height,
            "dtype": src.dtypes[0],
            "nodata": src.nodata,
            "count": src.count,
        }
    return data, meta


def normalize_to_uint8(data: np.ndarray, nodata=None) -> np.ndarray:
    """Normalize array to 0-255 uint8 with contrast enhancement.

    Uses percentile-based clipping (2nd-98th) to maximize contrast,
    then stretches to full 0-255 range. This is critical for LIDAR
    slope/LRM data which often has very low dynamic range.
    """
    arr = data.astype(np.float64)
    if nodata is not None:
        mask = arr == nodata
        arr = np.where(mask, np.nan, arr)

    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return np.zeros_like(data, dtype=np.uint8)

    # Percentile clip for contrast enhancement
    vmin = np.percentile(valid, 2)
    vmax = np.percentile(valid, 98)
    if vmax - vmin == 0:
        vmin = np.nanmin(arr)
        vmax = np.nanmax(arr)
    if vmax - vmin == 0:
        return np.zeros_like(data, dtype=np.uint8)

    normalized = np.clip((arr - vmin) / (vmax - vmin), 0, 1) * 255
    normalized = np.nan_to_num(normalized, nan=0)
    return normalized.astype(np.uint8)


if __name__ == "__main__":
    tiles = discover_tiles()
    print(f"Discovered {len(tiles)} tiles")
    for tid, info in list(tiles.items())[:3]:
        print(f"  {tid}: {info.available_layers}")
        for layer, path in info.layers.items():
            _, meta = read_tile(path)
            print(f"    {layer}: {meta['width']}x{meta['height']}, CRS={meta['crs']}, dtype={meta['dtype']}")
