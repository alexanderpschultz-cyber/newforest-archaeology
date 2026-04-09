#!/usr/bin/env python3
"""Build an interactive Folium web map of detections."""

import json
import sys
from pathlib import Path

import folium
from folium.plugins import MarkerCluster

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import OUTPUT_DIR
from pipeline.db import get_connection, get_all_detections

# Marker colors by feature type
TYPE_COLORS = {
    "barrow": "red",
    "enclosure": "blue",
    "field system": "green",
    "trackway": "orange",
    "hollow way": "orange",
    "platform": "purple",
    "charcoal hearth": "darkred",
    "pond bay": "cadetblue",
    "pillow mound": "pink",
    "earthwork": "beige",
    "ditch": "lightblue",
    "bank": "lightgreen",
}

CONFIDENCE_ICONS = {
    "high": "star",
    "medium": "info-sign",
    "low": "question-sign",
}


def build_map(output_path: Path | None = None):
    """Generate an interactive HTML map of all detections."""
    conn = get_connection()
    detections = get_all_detections(conn)
    conn.close()

    # Center on New Forest
    center_lat, center_lon = 50.87, -1.60
    m = folium.Map(location=[center_lat, center_lon], zoom_start=11,
                   tiles="OpenStreetMap")

    # Add satellite imagery option
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
    ).add_to(m)

    # Group markers by confidence
    high_group = folium.FeatureGroup(name="High confidence", show=True)
    med_group = folium.FeatureGroup(name="Medium confidence", show=True)
    low_group = folium.FeatureGroup(name="Low confidence", show=False)

    cluster = MarkerCluster()

    for det in detections:
        lat = det.get("centroid_lat")
        lon = det.get("centroid_lon")
        if lat is None or lon is None:
            continue

        ftype = det.get("feature_type", "unknown").lower()
        confidence = det.get("confidence", "low").lower()
        color = TYPE_COLORS.get(ftype, "gray")
        icon = CONFIDENCE_ICONS.get(confidence, "question-sign")

        popup_html = f"""
        <b>{det.get('feature_type', 'Unknown')}</b><br>
        <b>Confidence:</b> {confidence}<br>
        <b>Tile:</b> {det.get('tile_id', '')}<br>
        <b>BNG:</b> {det.get('centroid_easting', ''):.0f}E, {det.get('centroid_northing', ''):.0f}N<br>
        <b>Description:</b> {det.get('description', '')}<br>
        <b>Review:</b> {det.get('review_status', 'pending')}
        """

        marker = folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{det.get('feature_type', '?')} ({confidence})",
            icon=folium.Icon(color=color, icon=icon, prefix="glyphicon"),
        )

        if confidence == "high":
            marker.add_to(high_group)
        elif confidence == "medium":
            marker.add_to(med_group)
        else:
            marker.add_to(low_group)

    high_group.add_to(m)
    med_group.add_to(m)
    low_group.add_to(m)
    folium.LayerControl().add_to(m)

    if output_path is None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / "map.html"

    m.save(str(output_path))
    print(f"Map saved to {output_path}")
    print(f"Total markers: {len(detections)}")
    return output_path


if __name__ == "__main__":
    build_map()
