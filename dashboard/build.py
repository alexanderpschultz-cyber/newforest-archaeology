#!/usr/bin/env python3
"""Build the static dashboard site from detection results."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import COMPOSITES_DIR
from pipeline.db import get_connection
from pipeline.tile_loader import discover_tiles, read_tile, normalize_to_uint8
from pipeline.composite import make_composite
from PIL import Image

DASHBOARD_DIR = Path(__file__).parent
IMG_DIR = DASHBOARD_DIR / "img"
DATA_DIR = DASHBOARD_DIR / "data"


def export_data():
    """Export detections and tile info as JSON for the dashboard."""
    conn = get_connection()

    detections = []
    for d in conn.execute("""
        SELECT id, tile_id, patch_id, feature_type, confidence, description,
               x_percent, y_percent, centroid_easting, centroid_northing,
               centroid_lat, centroid_lon, reviewed, review_status
        FROM detections ORDER BY confidence DESC, tile_id
    """).fetchall():
        d = dict(d)
        if d["centroid_lat"] is None:
            continue
        detections.append(d)

    # Summary stats
    total = len(detections)
    by_type = {}
    by_confidence = {"high": 0, "medium": 0, "low": 0}
    for d in detections:
        ft = d["feature_type"]
        by_type[ft] = by_type.get(ft, 0) + 1
        conf = d.get("confidence", "low")
        if conf in by_confidence:
            by_confidence[conf] += 1

    tiles_processed = conn.execute(
        "SELECT COUNT(*) FROM tiles WHERE processed_coarse = TRUE"
    ).fetchone()[0]
    tiles_with_features = conn.execute(
        "SELECT COUNT(*) FROM tiles WHERE has_features = TRUE"
    ).fetchone()[0]

    conn.close()

    data = {
        "detections": detections,
        "stats": {
            "total_detections": total,
            "tiles_processed": tiles_processed,
            "tiles_with_features": tiles_with_features,
            "by_type": by_type,
            "by_confidence": by_confidence,
        },
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "detections.json", "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported {total} detections to data/detections.json")


def generate_gallery_images():
    """Generate cropped patch images for each detection."""
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_connection()
    detections = conn.execute("""
        SELECT id, tile_id, x_percent, y_percent FROM detections
        WHERE centroid_lat IS NOT NULL
    """).fetchall()
    conn.close()

    tiles = discover_tiles()
    composite_cache = {}

    for d in detections:
        d = dict(d)
        tile_id = d["tile_id"]
        det_id = d["id"]

        out_path = IMG_DIR / f"det_{det_id}.jpg"
        if out_path.exists():
            continue

        # Get or create composite
        if tile_id not in composite_cache:
            if tile_id not in tiles:
                continue
            comp = make_composite(tiles[tile_id])
            if comp is None:
                continue
            composite_cache[tile_id] = comp

        composite = composite_cache[tile_id]
        w, h = composite.size

        # Crop a 200x200 region centered on the detection
        x_pct = d.get("x_percent") or 50
        y_pct = d.get("y_percent") or 50
        cx = int(x_pct / 100 * w)
        cy = int(y_pct / 100 * h)
        crop_size = 200
        half = crop_size // 2

        x1 = max(0, cx - half)
        y1 = max(0, cy - half)
        x2 = min(w, x1 + crop_size)
        y2 = min(h, y1 + crop_size)
        x1 = max(0, x2 - crop_size)
        y1 = max(0, y2 - crop_size)

        patch = composite.crop((x1, y1, x2, y2)).convert("RGB")
        patch.save(out_path, "JPEG", quality=85)

    print(f"Generated gallery images for {len(detections)} detections")


if __name__ == "__main__":
    print("Building dashboard...")
    export_data()
    generate_gallery_images()
    print("Done. Open dashboard/index.html or deploy to GitHub Pages.")
