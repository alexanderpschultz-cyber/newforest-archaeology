#!/usr/bin/env python3
"""Main pipeline orchestrator for archaeological feature detection."""

import argparse
import sys
from pathlib import Path

from tqdm import tqdm

from config import COMPOSITES_DIR, DB_PATH
from pipeline.tile_loader import discover_tiles, read_tile
from pipeline.composite import make_composite, save_composite
from pipeline.patch_generator import generate_patches
from pipeline.detector import coarse_detect, fine_detect
from pipeline.georef import pixel_percent_to_bng, bng_to_wgs84
from pipeline.db import (
    init_db, get_connection, save_tile, save_coarse_result,
    save_detection, mark_fine_processed, get_unprocessed_tiles,
)


def run_coarse_pass(tile_ids: list[str] | None = None):
    """Run coarse detection on all (or specified) tiles."""
    tiles = discover_tiles()
    conn = get_connection()

    # Register tiles in DB
    for tid, info in tiles.items():
        if info.layers:
            first_layer = list(info.layers.values())[0]
            _, meta = read_tile(first_layer)
            save_tile(conn, tid, info.easting, info.northing,
                      meta["width"], meta["height"], str(meta["crs"]))

    # Get tiles to process
    if tile_ids:
        to_process = [tid for tid in tile_ids if tid in tiles]
    else:
        to_process = get_unprocessed_tiles(conn, "coarse")

    print(f"Coarse pass: {len(to_process)} tiles to process")

    for tile_id in tqdm(to_process, desc="Coarse detection"):
        tile = tiles[tile_id]
        composite = make_composite(tile)
        if composite is None:
            continue

        # Save composite for reference
        save_composite(tile, COMPOSITES_DIR)

        raw, parsed = coarse_detect(composite)
        if parsed is None:
            parsed = {"has_features": False, "summary": f"Parse error: {raw[:200]}"}
            print(f"  WARNING: Could not parse response for {tile_id}")

        save_coarse_result(conn, tile_id, parsed)

        has = parsed.get("has_features", False)
        summary = parsed.get("summary", "")
        tqdm.write(f"  {tile_id}: features={'YES' if has else 'no'} — {summary[:80]}")

    conn.close()


def run_fine_pass(tile_ids: list[str] | None = None):
    """Run fine-grained detection on tiles flagged in coarse pass."""
    tiles = discover_tiles()
    conn = get_connection()

    if tile_ids:
        to_process = [tid for tid in tile_ids if tid in tiles]
    else:
        to_process = get_unprocessed_tiles(conn, "fine")

    print(f"Fine pass: {len(to_process)} tiles to process")

    for tile_id in tqdm(to_process, desc="Fine detection"):
        tile = tiles[tile_id]
        composite = make_composite(tile)
        if composite is None:
            continue

        patches = generate_patches(composite, tile_id)
        tqdm.write(f"  {tile_id}: {len(patches)} patches")

        for patch in patches:
            raw, parsed = fine_detect(patch.image)
            if parsed is None:
                tqdm.write(f"    WARNING: Parse error on {patch.patch_id}")
                continue

            features = parsed.get("features", [])
            for feat in features:
                # Convert relative position within patch to tile-level position
                px = feat.get("x_percent")
                py = feat.get("y_percent")
                if px is not None and py is not None:
                    # Map patch-local % to tile-level %
                    tile_x_pct = (patch.x_offset + (px / 100) * patch.image.width) / composite.width * 100
                    tile_y_pct = (patch.y_offset + (py / 100) * patch.image.height) / composite.height * 100
                    feat["x_percent"] = tile_x_pct
                    feat["y_percent"] = tile_y_pct

                    # Compute geographic coordinates
                    e, n = pixel_percent_to_bng(tile_x_pct, tile_y_pct,
                                                tile.easting, tile.northing)
                    lat, lon = bng_to_wgs84(e, n)
                    feat["centroid_easting"] = e
                    feat["centroid_northing"] = n
                    feat["centroid_lat"] = lat
                    feat["centroid_lon"] = lon

                save_detection(conn, tile_id, patch.patch_id, feat, raw)

            if features:
                tqdm.write(f"    {patch.patch_id}: {len(features)} features found")

        mark_fine_processed(conn, tile_id)

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="New Forest LIDAR Archaeological Detection Pipeline")
    parser.add_argument("stage", choices=["coarse", "fine", "both"],
                        help="Which stage to run")
    parser.add_argument("--tiles", nargs="*",
                        help="Specific tile IDs to process (default: all unprocessed)")
    parser.add_argument("--init-db", action="store_true",
                        help="Initialize/reset the database")
    args = parser.parse_args()

    if args.init_db or not DB_PATH.exists():
        print("Initializing database...")
        init_db()

    if args.stage in ("coarse", "both"):
        run_coarse_pass(args.tiles)

    if args.stage in ("fine", "both"):
        run_fine_pass(args.tiles)

    print("Done.")


if __name__ == "__main__":
    main()
