#!/usr/bin/env python3
"""Export detections to GeoJSON format."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import DB_PATH, OUTPUT_DIR
from pipeline.db import get_connection, get_all_detections
from pipeline.georef import pixel_percent_to_bng, bng_to_wgs84


def export_geojson(output_path: Path | None = None, min_confidence: str | None = None):
    """Export all detections as a GeoJSON FeatureCollection."""
    conn = get_connection()
    detections = get_all_detections(conn)
    conn.close()

    confidence_rank = {"high": 3, "medium": 2, "low": 1}

    features = []
    for det in detections:
        # Filter by confidence if requested
        if min_confidence:
            det_rank = confidence_rank.get(det["confidence"], 0)
            min_rank = confidence_rank.get(min_confidence, 0)
            if det_rank < min_rank:
                continue

        lat = det.get("centroid_lat")
        lon = det.get("centroid_lon")
        if lat is None or lon is None:
            continue

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": det["id"],
                "tile_id": det["tile_id"],
                "patch_id": det["patch_id"],
                "feature_type": det["feature_type"],
                "confidence": det["confidence"],
                "description": det["description"],
                "easting": det.get("centroid_easting"),
                "northing": det.get("centroid_northing"),
                "reviewed": det.get("reviewed", False),
                "review_status": det.get("review_status"),
            },
        }
        features.append(feature)

    geojson = {
        "type": "FeatureCollection",
        "features": features,
    }

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "detections.geojson"

    with open(output_path, "w") as f:
        json.dump(geojson, f, indent=2)

    print(f"Exported {len(features)} features to {output_path}")
    return output_path


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-confidence", choices=["low", "medium", "high"])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    export_geojson(args.output, args.min_confidence)
