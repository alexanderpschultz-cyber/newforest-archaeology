#!/usr/bin/env python3
"""Simple Flask app for reviewing archaeological detections."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template_string, request, redirect, url_for
from config import DB_PATH, COMPOSITES_DIR
from pipeline.db import get_connection

app = Flask(__name__)

TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>New Forest Archaeology - Review</title>
    <style>
        body { font-family: system-ui, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }
        h1 { color: #e94560; }
        .stats { display: flex; gap: 20px; margin: 20px 0; }
        .stat { background: #16213e; padding: 15px 25px; border-radius: 8px; }
        .stat .num { font-size: 2em; font-weight: bold; color: #e94560; }
        table { border-collapse: collapse; width: 100%; background: #16213e; border-radius: 8px; overflow: hidden; }
        th, td { padding: 10px 15px; text-align: left; border-bottom: 1px solid #0f3460; }
        th { background: #0f3460; }
        tr:hover { background: #1a1a40; }
        .conf-high { color: #4ecca3; font-weight: bold; }
        .conf-medium { color: #f9a825; }
        .conf-low { color: #999; }
        .btn { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; color: white; font-size: 0.9em; }
        .btn-confirm { background: #4ecca3; }
        .btn-reject { background: #e94560; }
        .btn-uncertain { background: #f9a825; color: #333; }
        .filter { margin: 15px 0; }
        .filter select, .filter input { padding: 8px; border-radius: 4px; border: 1px solid #0f3460; background: #16213e; color: #eee; }
        a { color: #4ecca3; }
    </style>
</head>
<body>
    <h1>New Forest Archaeological Detections</h1>

    <div class="stats">
        <div class="stat"><div class="num">{{ stats.total }}</div>Total detections</div>
        <div class="stat"><div class="num">{{ stats.reviewed }}</div>Reviewed</div>
        <div class="stat"><div class="num">{{ stats.confirmed }}</div>Confirmed</div>
        <div class="stat"><div class="num">{{ stats.high }}</div>High confidence</div>
    </div>

    <div class="filter">
        <form method="get">
            <select name="confidence">
                <option value="">All confidence</option>
                <option value="high" {{ 'selected' if filter_conf == 'high' }}>High</option>
                <option value="medium" {{ 'selected' if filter_conf == 'medium' }}>Medium</option>
                <option value="low" {{ 'selected' if filter_conf == 'low' }}>Low</option>
            </select>
            <select name="status">
                <option value="">All status</option>
                <option value="pending" {{ 'selected' if filter_status == 'pending' }}>Pending</option>
                <option value="confirmed" {{ 'selected' if filter_status == 'confirmed' }}>Confirmed</option>
                <option value="rejected" {{ 'selected' if filter_status == 'rejected' }}>Rejected</option>
                <option value="uncertain" {{ 'selected' if filter_status == 'uncertain' }}>Uncertain</option>
            </select>
            <select name="type">
                <option value="">All types</option>
                {% for t in types %}
                <option value="{{ t }}" {{ 'selected' if filter_type == t }}>{{ t }}</option>
                {% endfor %}
            </select>
            <input type="submit" value="Filter" class="btn btn-confirm">
        </form>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>Tile</th>
            <th>Type</th>
            <th>Confidence</th>
            <th>Description</th>
            <th>BNG</th>
            <th>Status</th>
            <th>Actions</th>
        </tr>
        {% for d in detections %}
        <tr>
            <td>{{ d.id }}</td>
            <td>{{ d.tile_id }}</td>
            <td>{{ d.feature_type }}</td>
            <td class="conf-{{ d.confidence }}">{{ d.confidence }}</td>
            <td>{{ d.description[:100] }}</td>
            <td>{{ '%.0f'|format(d.centroid_easting or 0) }}E {{ '%.0f'|format(d.centroid_northing or 0) }}N</td>
            <td>{{ d.review_status or 'pending' }}</td>
            <td>
                <form method="post" action="/review/{{ d.id }}" style="display:inline">
                    <button name="status" value="confirmed" class="btn btn-confirm">&#10003;</button>
                    <button name="status" value="rejected" class="btn btn-reject">&#10007;</button>
                    <button name="status" value="uncertain" class="btn btn-uncertain">?</button>
                </form>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""


@app.route("/")
def index():
    conn = get_connection()

    # Stats
    stats = {
        "total": conn.execute("SELECT COUNT(*) FROM detections").fetchone()[0],
        "reviewed": conn.execute("SELECT COUNT(*) FROM detections WHERE reviewed = TRUE").fetchone()[0],
        "confirmed": conn.execute("SELECT COUNT(*) FROM detections WHERE review_status = 'confirmed'").fetchone()[0],
        "high": conn.execute("SELECT COUNT(*) FROM detections WHERE confidence = 'high'").fetchone()[0],
    }

    # Filters
    filter_conf = request.args.get("confidence", "")
    filter_status = request.args.get("status", "")
    filter_type = request.args.get("type", "")

    query = "SELECT * FROM detections WHERE 1=1"
    params = []
    if filter_conf:
        query += " AND confidence = ?"
        params.append(filter_conf)
    if filter_status == "pending":
        query += " AND (review_status IS NULL OR review_status = '')"
    elif filter_status:
        query += " AND review_status = ?"
        params.append(filter_status)
    if filter_type:
        query += " AND feature_type = ?"
        params.append(filter_type)

    query += " ORDER BY confidence DESC, tile_id"
    detections = [dict(r) for r in conn.execute(query, params).fetchall()]

    types = [r[0] for r in conn.execute(
        "SELECT DISTINCT feature_type FROM detections ORDER BY feature_type"
    ).fetchall()]

    conn.close()
    return render_template_string(TEMPLATE, detections=detections, stats=stats,
                                  types=types, filter_conf=filter_conf,
                                  filter_status=filter_status, filter_type=filter_type)


@app.route("/review/<int:det_id>", methods=["POST"])
def review(det_id):
    status = request.form.get("status")
    conn = get_connection()
    conn.execute(
        "UPDATE detections SET reviewed = TRUE, review_status = ? WHERE id = ?",
        (status, det_id),
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("index"))


if __name__ == "__main__":
    print("Starting review app at http://localhost:5001")
    app.run(port=5001, debug=True)
