#!/usr/bin/env python3
"""
Create the /executeAiQueryStreaming MySQL Monitoring dashboard on OpenSearch Dashboards.

Push to staging first, verify in the UI, then run against prod with explicit approval.

Usage:
    cd ~/h/source/elk
    python3 dashboards/scripts/create_execute_ai_query_streaming_mysql.py staging
    python3 dashboards/scripts/create_execute_ai_query_streaming_mysql.py prod   # after review

Dashboard id (stable across envs): f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from osd_builder import (
    avg,
    count,
    create_viz,
    date_histo,
    horizontal_bar_vis_state,
    line_vis_state,
    markdown_vis_state,
    percentiles,
    sum_,
    terms,
)
from osd_common import OsdClient

DASHBOARD_ID = "f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78"

# Viz-level base filter — route is applied at the dashboard level (query bar).
BASE_QUERY = 'msg:"outgoing non crud log line of"'

# Default route shown in the dashboard query bar. Users can change this to
# /executeAiQuery or /executeAiFieldPreviewQuery to compare other routes.
DASHBOARD_DEFAULT_ROUTE = "/executeAiQueryStreaming"

HOSTS = {
    "alpha": "opensearch-applogs.alpha-shadowbox.cloud",
    "staging": "opensearch-applogs.staging-shadowbox.cloud",
    "prod": "opensearch-applogs.shadowbox.cloud",
}


def _create_markdown_viz(client: OsdClient, title: str, markdown: str) -> str:
    """Create a Markdown viz with no index-pattern reference. Returns the viz id."""
    viz_id = str(uuid.uuid4())
    state = markdown_vis_state(title, markdown, font_size=11)
    body = {
        "attributes": {
            "title": title,
            "description": "",
            "visState": json.dumps(state),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(
                    {"query": {"query": "", "language": "kuery"}, "filter": []}
                )
            },
        },
        "references": [],
        "migrationVersion": {"visualization": "7.10.0"},
    }
    r = client.post(f"/api/saved_objects/visualization/{viz_id}", body)
    if r["status"] not in (200, 201):
        print(f"ERROR creating markdown viz {slug!r}: {r}", file=sys.stderr)
        sys.exit(1)
    return viz_id


def _create_dashboard(
    client: OsdClient,
    panel_ids: list[str],
) -> None:
    """Create the dashboard object with all panels pre-wired."""
    PANEL_LAYOUT = [
        # (panel_index, x, y, w, h)
        ("p1", 0, 0, 48, 15),   # request rate — full width
        ("p2", 0, 15, 24, 15),  # mysql queries avg+p95
        ("p3", 24, 15, 24, 15), # mysql duration p50/p95/p99
        ("p4", 0, 30, 24, 15),  # mysql vs total time
        ("p5", 24, 30, 24, 15), # shard-role setup note
        ("p6", 0, 45, 24, 20),  # top-20 users
        ("p7", 24, 45, 24, 20), # top-20 apps by mysql cost
    ]
    panels_json = []
    references = []
    for (idx, x, y, w, h), viz_id in zip(PANEL_LAYOUT, panel_ids):
        panels_json.append({
            "version": "7.10.0",
            "type": "visualization",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": idx},
            "panelIndex": idx,
            "embeddableConfig": {},
            "panelRefName": idx,
        })
        references.append({"id": viz_id, "name": idx, "type": "visualization"})

    body = {
        "attributes": {
            "title": "SRS - MySQL Monitoring",
            "description": (
                "MySQL query cost, latency, and traffic patterns for SRS routes. "
                "Default view: /executeAiQueryStreaming. "
                "Change the query bar to any routePattern to compare."
            ),
            "panelsJSON": json.dumps(panels_json),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": True,
            "timeFrom": "now-24h",
            "timeTo": "now",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {
                        "language": "kuery",
                        "query": f'routePattern:"{DASHBOARD_DEFAULT_ROUTE}"',
                    },
                    "filter": [],
                    "highlightAll": True,
                    "version": True,
                })
            },
        },
        "references": references,
        "migrationVersion": {"dashboard": "7.9.3"},
    }
    r = client.post(f"/api/saved_objects/dashboard/{DASHBOARD_ID}", body)
    if r["status"] == 409:
        print(
            f"Dashboard {DASHBOARD_ID} already exists on this env. "
            "Delete it in the UI first, or use osd_import --overwrite to replace it.",
            file=sys.stderr,
        )
        sys.exit(1)
    if r["status"] not in (200, 201):
        print(f"ERROR creating dashboard: {r}", file=sys.stderr)
        sys.exit(1)


def main(env: str) -> None:
    client = OsdClient(env)

    # Panel 1 — request rate split by status class (stacked line)
    aggs1 = [
        count("1"),
        date_histo("2"),
        terms("3", field="statusClass", size=5, schema="group", label="status class"),
    ]
    state1 = line_vis_state(
        "Request Rate by Status Class", aggs1, y_title="requests/bucket"
    )
    state1["params"]["seriesParams"][0]["mode"] = "stacked"
    id1 = create_viz(
        client,
        "Request Rate by Status Class",
        "count() per bucket split by statusClass — baseline traffic + error regressions in one view",
        BASE_QUERY,
        state1,
    )
    print(f"  panel 1  {id1}")

    # Panel 2 — MySQL queries per request: avg + p95 (two series, one chart)
    aggs2 = [
        avg("1", "mysqlNumQueries", label="avg"),
        percentiles("2", "mysqlNumQueries", percents=[95], label="p95"),
        date_histo("3"),
    ]
    state2 = line_vis_state(
        "MySQL Queries per Request — avg + p95", aggs2, y_title="queries"
    )
    state2["params"]["seriesParams"].append({
        "show": True, "type": "line", "mode": "normal",
        "data": {"label": "p95", "id": "2"},
        "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
        "lineWidth": 2, "showCircles": False, "interpolate": "linear",
    })
    id2 = create_viz(
        client,
        "MySQL Queries per Request — avg + p95",
        "avg + p95 of mysqlNumQueries — watch for a flat step-up after the forgery-fix deploy",
        BASE_QUERY,
        state2,
    )
    print(f"  panel 2  {id2}")

    # Panel 3 — MySQL duration distribution: p50 / p95 / p99
    aggs3 = [
        percentiles("1", "mysqlDurationMs", percents=[50, 95, 99]),
        date_histo("2"),
    ]
    state3 = line_vis_state(
        "MySQL Duration (p50 / p95 / p99)", aggs3, y_title="ms"
    )
    id3 = create_viz(
        client,
        "MySQL Duration (p50 / p95 / p99)",
        "p50/p95/p99 of mysqlDurationMs — p99 movement = slow shard or bad query plan",
        BASE_QUERY,
        state3,
    )
    print(f"  panel 3  {id3}")

    # Panel 4 — MySQL share of total request time (overlaid area)
    # Shows avg(mysqlDurationMs) and avg(durationMs) as filled overlapping series.
    # The mysql area sits inside the total area — rising mysql slice at flat total = regression.
    # Note: OSD basic vis cannot compute durationMs - mysqlDurationMs directly;
    # use TSVB if you need the exact "other" series.
    aggs4 = [
        avg("1", "mysqlDurationMs", label="mysql"),
        avg("2", "durationMs", label="total (LLM + mysql + other)"),
        date_histo("3"),
    ]
    state4 = line_vis_state(
        "MySQL Share of Total Request Time", aggs4, y_title="ms (avg)"
    )
    p4 = state4["params"]
    p4["seriesParams"][0]["fill"] = 0.4
    p4["seriesParams"].append({
        "show": True, "type": "line", "mode": "normal", "fill": 0.4,
        "data": {"label": "total (LLM + mysql + other)", "id": "2"},
        "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
        "lineWidth": 2, "showCircles": False, "interpolate": "linear",
    })
    id4 = create_viz(
        client,
        "MySQL Share of Total Request Time",
        "avg(mysqlDurationMs) vs avg(durationMs) overlaid — rising mysql at flat total = regression",
        BASE_QUERY,
        state4,
    )
    print(f"  panel 4  {id4}")

    # Panel 5 — Shard role breakdown (setup note, markdown)
    # databaseQueriesByRegionAndDbShardRole is a stringified JSON blob; aggregating on
    # sub-keys requires a Painless scripted field in the index pattern first.
    shard_md = """\
### Queries by Shard Role — setup required

`databaseQueriesByRegionAndDbShardRole` is a stringified JSON blob (e.g. `{"us-east-1":{"main":6,"applicationLive":15}}`).
To plot shard-role counts over time, add **two scripted fields** to the `airtable-applogs-index` index pattern:

| Field name | Type | Painless script |
|---|---|---|
| `mysqlQueriesMain` | number | see below |
| `mysqlQueriesApplicationLive` | number | see below |

**Script for `mysqlQueriesMain`:**
```
def raw = doc.containsKey('databaseQueriesByRegionAndDbShardRole') ? doc['databaseQueriesByRegionAndDbShardRole'].value : null;
if (raw == null || raw.isEmpty()) return 0;
def obj = params._source.get('databaseQueriesByRegionAndDbShardRole');
if (obj == null) return 0;
try {
  int total = 0;
  for (def region : ((Map)new groovy.json.JsonSlurper().parseText(obj)).values()) {
    if (((Map)region).containsKey('main')) total += ((Map)region).get('main');
  }
  return total;
} catch(e) { return 0; }
```

Once the fields are added, replace this panel with a stacked bar: `sum(mysqlQueriesMain)` + `sum(mysqlQueriesApplicationLive)` split by date_histo.
"""
    id5 = _create_markdown_viz(client, "Queries by Shard Role", shard_md)
    print(f"  panel 5  {id5}")

    # Panel 6 — top-20 users by request volume (last 24h horizontal bar)
    aggs6 = [
        count("1"),
        terms("2", field="userId", size=20, order_by="1", schema="segment", label="user"),
    ]
    state6 = horizontal_bar_vis_state(
        "Top 20 Users by Request Volume", aggs6, y_title="requests"
    )
    id6 = create_viz(
        client,
        "Top 20 Users by Request Volume",
        "identify hot integrations, abuse patterns, test accounts skewing aggregates",
        BASE_QUERY,
        state6,
    )
    print(f"  panel 6  {id6}")

    # Panel 7 — top-20 applications by MySQL cost (last 24h horizontal bar)
    aggs7 = [
        sum_("1", "mysqlNumQueries"),
        terms(
            "2",
            field="applicationId",
            size=20,
            order_by="1",
            schema="segment",
            label="application",
        ),
    ]
    state7 = horizontal_bar_vis_state(
        "Top 20 Applications by MySQL Cost", aggs7, y_title="total MySQL queries"
    )
    id7 = create_viz(
        client,
        "Top 20 Applications by MySQL Cost",
        "which customer apps drive query load through this endpoint",
        BASE_QUERY,
        state7,
    )
    print(f"  panel 7  {id7}")

    print(f"\nCreating dashboard {DASHBOARD_ID} — title: SRS - MySQL Monitoring")
    _create_dashboard(client, [id1, id2, id3, id4, id5, id6, id7])

    host = HOSTS[env]
    print(f"\nDashboard live on {env}:")
    print(f"  https://{host}/_dashboards/app/dashboards#/view/{DASHBOARD_ID}\n")
    if env != "prod":
        print(
            "Review in the UI, then run against prod when ready:\n"
            f"  python3 dashboards/scripts/create_execute_ai_query_streaming_mysql.py prod"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("alpha", "staging", "prod"):
        print(
            "Usage: python3 create_execute_ai_query_streaming_mysql.py <alpha|staging|prod>",
            file=sys.stderr,
        )
        sys.exit(1)
    main(sys.argv[1])
