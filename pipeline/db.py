"""SQLite database for storing detection results."""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from config import DB_PATH


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = DB_PATH):
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tiles (
            tile_id TEXT PRIMARY KEY,
            easting INTEGER,
            northing INTEGER,
            width INTEGER,
            height INTEGER,
            crs TEXT,
            coarse_result TEXT,
            has_features BOOLEAN,
            processed_coarse BOOLEAN DEFAULT FALSE,
            processed_fine BOOLEAN DEFAULT FALSE,
            created_at DATETIME
        );

        CREATE TABLE IF NOT EXISTS detections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tile_id TEXT NOT NULL,
            patch_id TEXT,
            feature_type TEXT,
            confidence TEXT,
            description TEXT,
            x_percent REAL,
            y_percent REAL,
            centroid_easting REAL,
            centroid_northing REAL,
            centroid_lat REAL,
            centroid_lon REAL,
            raw_response TEXT,
            reviewed BOOLEAN DEFAULT FALSE,
            review_status TEXT,
            created_at DATETIME,
            FOREIGN KEY (tile_id) REFERENCES tiles(tile_id)
        );

        CREATE INDEX IF NOT EXISTS idx_detections_tile ON detections(tile_id);
        CREATE INDEX IF NOT EXISTS idx_detections_type ON detections(feature_type);
        CREATE INDEX IF NOT EXISTS idx_detections_confidence ON detections(confidence);
    """)
    conn.commit()
    conn.close()


def save_tile(conn: sqlite3.Connection, tile_id: str, easting: int, northing: int,
              width: int, height: int, crs: str):
    conn.execute(
        """INSERT OR IGNORE INTO tiles (tile_id, easting, northing, width, height, crs, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (tile_id, easting, northing, width, height, crs,
         datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def save_coarse_result(conn: sqlite3.Connection, tile_id: str, result: dict):
    conn.execute(
        """UPDATE tiles SET coarse_result = ?, has_features = ?, processed_coarse = TRUE
           WHERE tile_id = ?""",
        (json.dumps(result), result.get("has_features", False), tile_id),
    )
    conn.commit()


def save_detection(conn: sqlite3.Connection, tile_id: str, patch_id: str,
                   feature: dict, raw_response: str):
    conn.execute(
        """INSERT INTO detections
           (tile_id, patch_id, feature_type, confidence, description,
            x_percent, y_percent, centroid_easting, centroid_northing,
            centroid_lat, centroid_lon, raw_response, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            tile_id, patch_id,
            feature.get("type", "unknown"),
            feature.get("confidence", "unknown"),
            feature.get("description", ""),
            feature.get("x_percent"),
            feature.get("y_percent"),
            feature.get("centroid_easting"),
            feature.get("centroid_northing"),
            feature.get("centroid_lat"),
            feature.get("centroid_lon"),
            raw_response,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def mark_fine_processed(conn: sqlite3.Connection, tile_id: str):
    conn.execute("UPDATE tiles SET processed_fine = TRUE WHERE tile_id = ?", (tile_id,))
    conn.commit()


def get_unprocessed_tiles(conn: sqlite3.Connection, stage: str = "coarse") -> list[str]:
    if stage == "coarse":
        rows = conn.execute(
            "SELECT tile_id FROM tiles WHERE processed_coarse = FALSE"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT tile_id FROM tiles WHERE has_features = TRUE AND processed_fine = FALSE"
        ).fetchall()
    return [r["tile_id"] for r in rows]


def get_all_detections(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM detections ORDER BY tile_id, patch_id"
    ).fetchall()
    return [dict(r) for r in rows]
