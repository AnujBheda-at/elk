#!/usr/bin/env python3
"""
Create the generalized SRS dashboard on OpenSearch Dashboards.

Sections: Volume, Perf, Errors, MySQL.
Default filter: routePattern:"/executeAiQueryStreaming" as a filter pill.
Change or disable it in the filter bar to compare other routes.

Usage:
    cd ~/h/source/elk
    python3 dashboards/scripts/create_srs_general.py staging
    python3 dashboards/scripts/create_srs_general.py prod   # after review

Dashboard id (stable across envs): e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78
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
    histogram_vis_state,
    horizontal_bar_vis_state,
    line_vis_state,
    markdown_vis_state,
    percentiles,
    sum_,
    terms,
)
from osd_common import OsdClient, SAVED_OBJECTS_INDEX_PATTERN_ID

DASHBOARD_ID = "e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78"

BASE_QUERY = 'msg:"outgoing non crud log line of"'

HOSTS = {
    "alpha": "opensearch-applogs.alpha-shadowbox.cloud",
    "staging": "opensearch-applogs.staging-shadowbox.cloud",
    "prod": "opensearch-applogs.shadowbox.cloud",
}

ROUTE_FILTER = [{
    "meta": {
        "index": SAVED_OBJECTS_INDEX_PATTERN_ID,
        "negate": False,
        "disabled": False,
        "alias": None,
        "type": "phrase",
        "key": "routePattern",
        "params": {"query": "/executeAiQueryStreaming"},
        "value": "/executeAiQueryStreaming",
    },
    "query": {"match_phrase": {"routePattern": "/executeAiQueryStreaming"}},
    "$state": {"store": "appState"},
}]


def _heading_viz(client: OsdClient, label: str) -> str:
    """Create a section heading viz with a clean title. Returns viz id."""
    viz_id = str(uuid.uuid4())
    vis_state = {
        "title": label,
        "type": "markdown",
        "aggs": [],
        "params": {"fontSize": 14, "openLinksInNewTab": False, "markdown": f"## {label}"},
    }
    body = {
        "attributes": {
            "title": label,
            "description": "",
            "visState": json.dumps(vis_state),
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
        print(f"ERROR creating heading {label!r}: {r}", file=sys.stderr)
        sys.exit(1)
    return viz_id


def _markdown_viz(client: OsdClient, title: str, markdown: str) -> str:
    """Create a Markdown viz with no index-pattern reference. Returns viz id."""
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
        print(f"ERROR creating markdown viz {title!r}: {r}", file=sys.stderr)
        sys.exit(1)
    return viz_id


def _create_dashboard(client: OsdClient, panels: list[tuple]) -> None:
    """panels: list of (panel_index, x, y, w, h, viz_id, hide_title)"""
    panels_json = []
    references = []
    for idx, x, y, w, h, viz_id, hide_title in panels:
        panels_json.append({
            "version": "7.10.0",
            "type": "visualization",
            "gridData": {"x": x, "y": y, "w": w, "h": h, "i": idx},
            "panelIndex": idx,
            "embeddableConfig": {"hidePanelTitles": True} if hide_title else {},
            "panelRefName": idx,
        })
        references.append({"id": viz_id, "name": idx, "type": "visualization"})

    body = {
        "attributes": {
            "title": "SRS",
            "description": "",
            "panelsJSON": json.dumps(panels_json),
            "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
            "timeRestore": True,
            "timeFrom": "now-24h",
            "timeTo": "now",
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"language": "kuery", "query": ""},
                    "filter": ROUTE_FILTER,
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
            f"Dashboard {DASHBOARD_ID} already exists. "
            "Delete it in the UI first, or use osd_import --overwrite.",
            file=sys.stderr,
        )
        sys.exit(1)
    if r["status"] not in (200, 201):
        print(f"ERROR creating dashboard: {r}", file=sys.stderr)
        sys.exit(1)


def main(env: str) -> None:
    client = OsdClient(env)
    # (panel_index, x, y, w, h, viz_id, hide_title)
    panels: list[tuple] = []

    # ── Volume (y=0–35) ───────────────────────────────────────────────────────
    print("Volume section...")
    h_vol = _heading_viz(client, "Volume")
    panels.append(("h_vol", 0, 0, 48, 3, h_vol, True))

    aggs_v1 = [
        count("1"),
        date_histo("2"),
        terms("3", field="statusClass", size=5, schema="group", label="status class"),
    ]
    state_v1 = line_vis_state(
        "Request Rate by Status Class", aggs_v1, y_title="requests/bucket"
    )
    state_v1["params"]["seriesParams"][0]["mode"] = "normal"
    id_v1 = create_viz(client, "Request Rate by Status Class",
                       "count() split by statusClass — baseline traffic and error regressions",
                       BASE_QUERY, state_v1)
    panels.append(("v1", 0, 3, 48, 15, id_v1, False))
    print(f"  v1  {id_v1}")

    aggs_v2 = [
        count("1"),
        terms("2", field="routePattern", size=20, order_by="1", schema="segment", label="route"),
    ]
    id_v2 = create_viz(client, "Top 20 Routes by Volume",
                       "which SRS routes receive the most traffic",
                       BASE_QUERY, horizontal_bar_vis_state("Top 20 Routes by Volume", aggs_v2, y_title="requests"))
    panels.append(("v2", 0, 18, 24, 18, id_v2, False))
    print(f"  v2  {id_v2}")

    aggs_v3 = [
        count("1"),
        terms("2", field="userId", size=20, order_by="1", schema="segment", label="user"),
    ]
    id_v3 = create_viz(client, "Top 20 Users by Volume",
                       "hot integrations, abuse patterns, and test accounts skewing aggregates",
                       BASE_QUERY, horizontal_bar_vis_state("Top 20 Users by Volume", aggs_v3, y_title="requests"))
    panels.append(("v3", 24, 18, 24, 18, id_v3, False))
    print(f"  v3  {id_v3}")

    # ── Perf (y=36–53) ────────────────────────────────────────────────────────
    print("Perf section...")
    h_perf = _heading_viz(client, "Perf")
    panels.append(("h_perf", 0, 36, 48, 3, h_perf, True))

    aggs_p1 = [
        percentiles("1", "durationMs", percents=[50, 95, 99]),
        date_histo("2"),
    ]
    state_p1 = line_vis_state("Request Latency (p50 / p95 / p99)", aggs_p1, y_title="ms")
    state_p1["params"]["valueAxes"][0]["scale"]["type"] = "log"
    id_p1 = create_viz(client, "Request Latency (p50 / p95 / p99)",
                       "p50/p95/p99 of durationMs — p99 spike = tail-latency regression",
                       BASE_QUERY, state_p1)
    panels.append(("p1", 0, 39, 24, 15, id_p1, False))
    print(f"  p1  {id_p1}")

    aggs_p2 = [
        avg("1", "durationMs", label="avg duration (ms)"),
        terms("2", field="routePattern", size=20, order_by="1", schema="segment", label="route"),
    ]
    state_p2 = horizontal_bar_vis_state("Top 20 Routes by Avg Duration", aggs_p2, y_title="avg ms")
    state_p2["params"]["valueAxes"][0]["scale"]["type"] = "log"
    id_p2 = create_viz(client, "Top 20 Routes by Avg Duration",
                       "which routes have the highest average end-to-end latency",
                       BASE_QUERY, state_p2)
    panels.append(("p2", 24, 39, 24, 15, id_p2, False))
    print(f"  p2  {id_p2}")

    # ── Errors (y=54–71) ──────────────────────────────────────────────────────
    print("Errors section...")
    h_err = _heading_viz(client, "Errors")
    panels.append(("h_err", 0, 54, 48, 3, h_err, True))

    err_query = BASE_QUERY + " AND statusClass:serverError"
    aggs_e1 = [count("1"), date_histo("2")]
    id_e1 = create_viz(client, "Server Errors Over Time",
                       "count of statusClass:serverError — spike = active incident",
                       err_query, line_vis_state("Server Errors Over Time", aggs_e1, y_title="errors/bucket"))
    panels.append(("e1", 0, 57, 24, 15, id_e1, False))
    print(f"  e1  {id_e1}")

    aggs_e2 = [
        count("1"),
        date_histo("2"),
        terms("3", field="statusClass", size=5, schema="group", label="status class"),
    ]
    id_e2 = create_viz(client, "Request Status Breakdown (%)",
                       "stacked 100% view of statusClass — rising error band = error-rate regression",
                       BASE_QUERY,
                       histogram_vis_state("Request Status Breakdown (%)", aggs_e2,
                                           y_title="% of requests", percentage=True))
    panels.append(("e2", 24, 57, 24, 15, id_e2, False))
    print(f"  e2  {id_e2}")

    # ── MySQL (y=72–122) ──────────────────────────────────────────────────────
    print("MySQL section...")
    h_mysql = _heading_viz(client, "MySQL")
    panels.append(("h_mysql", 0, 72, 48, 3, h_mysql, True))

    aggs_m1 = [
        avg("1", "mysqlNumQueries", label="avg"),
        percentiles("2", "mysqlNumQueries", percents=[95], label="p95"),
        date_histo("3"),
    ]
    state_m1 = line_vis_state("MySQL Queries per Request — avg + p95", aggs_m1, y_title="queries")
    state_m1["params"]["seriesParams"].append({
        "show": True, "type": "line", "mode": "normal",
        "data": {"label": "p95", "id": "2"},
        "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
        "lineWidth": 2, "showCircles": False, "interpolate": "linear",
    })
    id_m1 = create_viz(client, "MySQL Queries per Request — avg + p95",
                       "avg + p95 of mysqlNumQueries — step-up after deploy = regression",
                       BASE_QUERY, state_m1)
    panels.append(("m1", 0, 75, 24, 15, id_m1, False))
    print(f"  m1  {id_m1}")

    aggs_m2 = [
        percentiles("1", "mysqlDurationMs", percents=[50, 95, 99]),
        date_histo("2"),
    ]
    id_m2 = create_viz(client, "MySQL Duration (p50 / p95 / p99)",
                       "p50/p95/p99 of mysqlDurationMs — p99 movement = slow shard or bad query plan",
                       BASE_QUERY, line_vis_state("MySQL Duration (p50 / p95 / p99)", aggs_m2, y_title="ms"))
    panels.append(("m2", 24, 75, 24, 15, id_m2, False))
    print(f"  m2  {id_m2}")

    aggs_m3 = [
        avg("1", "mysqlDurationMs", label="mysql"),
        avg("2", "durationMs", label="total (LLM + mysql + other)"),
        date_histo("3"),
    ]
    state_m3 = line_vis_state("MySQL Share of Total Request Time", aggs_m3, y_title="ms (avg)")
    state_m3["params"]["seriesParams"][0]["fill"] = 0.4
    state_m3["params"]["seriesParams"].append({
        "show": True, "type": "line", "mode": "normal", "fill": 0.4,
        "data": {"label": "total (LLM + mysql + other)", "id": "2"},
        "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
        "lineWidth": 2, "showCircles": False, "interpolate": "linear",
    })
    id_m3 = create_viz(client, "MySQL Share of Total Request Time",
                       "avg(mysqlDurationMs) vs avg(durationMs) — rising mysql at flat total = regression",
                       BASE_QUERY, state_m3)
    panels.append(("m3", 0, 90, 24, 15, id_m3, False))
    print(f"  m3  {id_m3}")

    aggs_m5 = [
        sum_("1", "mysqlNumQueries"),
        terms("2", field="applicationId", size=20, order_by="1", schema="segment", label="application"),
    ]
    id_m5 = create_viz(client, "Top 20 Applications by MySQL Cost",
                       "which customer apps drive MySQL query load through SRS",
                       BASE_QUERY, horizontal_bar_vis_state("Top 20 Applications by MySQL Cost",
                                                            aggs_m5, y_title="total MySQL queries"))
    panels.append(("m5", 24, 90, 24, 18, id_m5, False))
    print(f"  m5  {id_m5}")

    shard_md = """\
### Queries by Shard Role — setup required

`databaseQueriesByRegionAndDbShardRole` is a stringified JSON blob.
Add two scripted fields to the index pattern to unlock this chart:

| Field | Painless target |
|---|---|
| `mysqlQueriesMain` | sum of `main` values across all regions |
| `mysqlQueriesApplicationLive` | sum of `applicationLive` values |

Once added, replace this panel with a stacked bar:
`sum(mysqlQueriesMain)` + `sum(mysqlQueriesApplicationLive)` split by date_histo.
"""
    id_m4 = _markdown_viz(client, "Queries by Shard Role", shard_md)
    panels.append(("m4", 0, 105, 24, 15, id_m4, False))
    print(f"  m4  {id_m4}")

    print(f"\nCreating dashboard {DASHBOARD_ID} — title: SRS")
    _create_dashboard(client, panels)

    host = HOSTS[env]
    print(f"\nDashboard live on {env}:")
    print(f"  https://{host}/_dashboards/app/dashboards#/view/{DASHBOARD_ID}\n")
    if env != "prod":
        print(
            "Review in the UI, then run against prod when ready:\n"
            "  python3 dashboards/scripts/create_srs_general.py prod"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("alpha", "staging", "prod"):
        print(
            "Usage: python3 create_srs_general.py <alpha|staging|prod>",
            file=sys.stderr,
        )
        sys.exit(1)
    main(sys.argv[1])
