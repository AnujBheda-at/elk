#!/usr/bin/env python3
"""
Reusable primitives for building and mutating OpenSearch Dashboards saved objects.

Design principle
----------------
Every factory function returns a plain Python dict. Callers mutate the dict freely
before passing it to create_viz() or anywhere else. There is no DSL, no builder
chain, no objects — just dicts all the way down.

If a factory doesn't expose a parameter you need, do one of two things:
  1. Mutate the returned dict directly (always works for one-off needs).
  2. Update the factory to add the parameter (preferred if you'll reuse the pattern).

Neither is a workaround. Both are intentional. The goal is cheap construction,
not enforced structure.

Quick reference
---------------
Agg builders      → count, avg, sum_, percentiles, date_histo, terms, filters_agg
Params builders   → line_params, histogram_params, horizontal_bar_params
Vis state         → line_vis_state, histogram_vis_state, horizontal_bar_vis_state,
                    table_vis_state, markdown_vis_state
API helpers       → create_viz, create_heading, add_panels_to_dashboard
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from osd_common import OsdClient, SAVED_OBJECTS_INDEX_PATTERN_ID

INDEX_REF_NAME = "kibanaSavedObjectMeta.searchSourceJSON.index"


# ---------------------------------------------------------------------------
# Agg builders — each returns a plain dict; mutate freely
# ---------------------------------------------------------------------------

def count(agg_id: str, label: str | None = None) -> dict:
    p: dict[str, Any] = {}
    if label:
        p["customLabel"] = label
    return {"id": agg_id, "enabled": True, "type": "count", "schema": "metric", "params": p}


def avg(agg_id: str, field: str, label: str | None = None) -> dict:
    p: dict[str, Any] = {"field": field}
    if label:
        p["customLabel"] = label
    return {"id": agg_id, "enabled": True, "type": "avg", "schema": "metric", "params": p}


def sum_(agg_id: str, field: str, label: str | None = None) -> dict:
    p: dict[str, Any] = {"field": field}
    if label:
        p["customLabel"] = label
    return {"id": agg_id, "enabled": True, "type": "sum", "schema": "metric", "params": p}


def percentiles(
    agg_id: str,
    field: str,
    percents: list[float] | None = None,
    label: str | None = None,
) -> dict:
    p: dict[str, Any] = {"field": field, "percents": percents or [50, 95, 99], "keyed": False}
    if label:
        p["customLabel"] = label
    return {"id": agg_id, "enabled": True, "type": "percentiles", "schema": "metric", "params": p}


def date_histo(
    agg_id: str,
    field: str = "@timestamp",
    interval: str = "auto",
) -> dict:
    return {
        "id": agg_id, "enabled": True, "type": "date_histogram", "schema": "segment",
        "params": {
            "field": field, "interval": interval, "useNormalizedEsInterval": True,
            "min_doc_count": 1, "drop_partials": False, "extended_bounds": {},
        },
    }


def terms(
    agg_id: str,
    field: str,
    size: int = 10,
    order: str = "desc",
    order_by: str = "1",
    schema: str = "group",
    other_bucket: bool = False,
    missing_bucket: bool = False,
    label: str | None = None,
) -> dict:
    """
    schema="group"   → split series (one line/bar per term value)
    schema="segment" → x-axis buckets (replaces date_histo for non-time top-N charts)
    """
    p: dict[str, Any] = {
        "field": field, "size": size, "order": order, "orderBy": order_by,
        "otherBucket": other_bucket, "otherBucketLabel": "Other",
        "missingBucket": missing_bucket,
    }
    if label:
        p["customLabel"] = label
    return {"id": agg_id, "enabled": True, "type": "terms", "schema": schema, "params": p}


def filters_agg(
    agg_id: str,
    filters: list[tuple[str, str]],
    schema: str = "group",
) -> dict:
    """
    filters: list of (kuery_query_string, display_label)

    Example:
        filters_agg("3", [
            ('msg:"Public API request timed out"', "Timeout"),
            ('msg:"Public API request returned non-200"', "Non-200"),
        ])
    """
    f_list = [
        {"input": {"query": q, "language": "kuery"}, "label": lbl}
        for q, lbl in filters
    ]
    return {"id": agg_id, "enabled": True, "type": "filters", "schema": schema,
            "params": {"filters": f_list}}


# ---------------------------------------------------------------------------
# Params builders — return plain dicts; mutate freely
# ---------------------------------------------------------------------------

def line_params(y_title: str = "count") -> dict:
    return {
        "type": "line",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear"},
            "labels": {"show": True, "filter": True, "truncate": 100}, "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
            "position": "left", "show": True, "style": {},
            "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": y_title},
        }],
        "seriesParams": [{
            "show": True, "type": "line", "mode": "normal",
            "data": {"label": y_title, "id": "1"},
            "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
            "lineWidth": 2, "showCircles": False, "interpolate": "linear",
        }],
        "addTooltip": True, "addLegend": True, "legendPosition": "right",
        "times": [], "addTimeMarker": False, "labels": {},
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
    }


def histogram_params(
    y_title: str = "count",
    stacked: bool = False,
    percentage: bool = False,
) -> dict:
    """
    stacked=True   → bars stacked (absolute)
    percentage=True → bars stacked as % of total (implies stacked)
    """
    scale_mode = "percentage" if percentage else "normal"
    series_mode = "stacked" if (stacked or percentage) else "normal"
    return {
        "type": "histogram",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "bottom",
            "show": True, "style": {}, "scale": {"type": "linear"},
            "labels": {"show": True, "filter": True, "truncate": 100}, "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value",
            "position": "left", "show": True, "style": {},
            "scale": {"type": "linear", "mode": scale_mode},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": y_title},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": series_mode,
            "data": {"label": y_title, "id": "1"},
            "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
            "lineWidth": 2, "showCircles": True,
        }],
        "addTooltip": True, "addLegend": True, "legendPosition": "right",
        "times": [], "addTimeMarker": False, "labels": {"show": False},
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
    }


def horizontal_bar_params(y_title: str = "count") -> dict:
    return {
        "type": "histogram",
        "grid": {"categoryLines": False, "valueAxis": "ValueAxis-1"},
        "categoryAxes": [{
            "id": "CategoryAxis-1", "type": "category", "position": "left",
            "show": True, "style": {}, "scale": {"type": "linear"},
            "labels": {"show": True, "filter": False, "truncate": 200}, "title": {},
        }],
        "valueAxes": [{
            "id": "ValueAxis-1", "name": "BottomAxis-1", "type": "value",
            "position": "bottom", "show": True, "style": {},
            "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": True, "truncate": 100},
            "title": {"text": y_title},
        }],
        "seriesParams": [{
            "show": True, "type": "histogram", "mode": "normal",
            "data": {"label": y_title, "id": "1"},
            "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True,
            "lineWidth": 2, "showCircles": True,
        }],
        "addTooltip": True, "addLegend": False, "legendPosition": "right",
        "times": [], "addTimeMarker": False, "labels": {},
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"},
    }


# ---------------------------------------------------------------------------
# Vis state composers — return a complete visState dict; mutate freely
# ---------------------------------------------------------------------------

def line_vis_state(title: str, aggs: list[dict], y_title: str = "count") -> dict:
    return {"title": title, "type": "line", "aggs": aggs, "params": line_params(y_title)}


def histogram_vis_state(
    title: str,
    aggs: list[dict],
    y_title: str = "count",
    stacked: bool = False,
    percentage: bool = False,
) -> dict:
    return {
        "title": title, "type": "histogram", "aggs": aggs,
        "params": histogram_params(y_title, stacked=stacked, percentage=percentage),
    }


def horizontal_bar_vis_state(
    title: str,
    aggs: list[dict],
    y_title: str = "count",
) -> dict:
    return {
        "title": title, "type": "horizontal_bar", "aggs": aggs,
        "params": horizontal_bar_params(y_title),
    }


def table_vis_state(title: str, aggs: list[dict], per_page: int = 10) -> dict:
    """
    Data table: metric + one or more split-row terms aggs.
    For split rows use terms() with schema="bucket" (the default).
    For the metric use count() or any metric agg with schema="metric".

    Example — three-level breakdown:
        table_vis_state("CRUD Failures", [
            count("1"),
            terms("2", "modelClassName", size=50, schema="bucket"),
            terms("3", "apiName",        size=10, schema="bucket"),
            terms("4", "action",         size=50, schema="bucket"),
        ])
    """
    return {
        "title": title,
        "type": "table",
        "aggs": aggs,
        "params": {
            "perPage": per_page,
            "showPartialRows": False,
            "showMetricsAtAllLevels": False,
            "showTotal": False,
            "totalFunc": "sum",
            "percentageCol": "",
        },
    }


def markdown_vis_state(title: str, markdown: str, font_size: int = 12) -> dict:
    return {
        "title": title, "type": "markdown", "aggs": [],
        "params": {"fontSize": font_size, "openLinksInNewTab": False, "markdown": markdown},
    }


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def create_viz(
    client: OsdClient,
    title: str,
    description: str,
    query: str,
    vis_state: dict,
    index_pattern_id: str = SAVED_OBJECTS_INDEX_PATTERN_ID,
) -> str:
    """
    POST a new visualization. Returns the saved-object id.

    vis_state is serialised as-is; mutate it before calling this function.
    The vis_state["title"] is overwritten with `title` to keep them in sync.
    """
    vis_state = dict(vis_state)  # shallow copy — don't mutate caller's dict
    vis_state["title"] = title

    viz_id = str(uuid.uuid4())
    search_source = json.dumps({
        "query": {"query": query, "language": "kuery"},
        "filter": [],
        "indexRefName": INDEX_REF_NAME,
    })
    body = {
        "attributes": {
            "title": title,
            "description": description,
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": search_source},
        },
        "references": [{"name": INDEX_REF_NAME, "type": "index-pattern", "id": index_pattern_id}],
        "migrationVersion": {"visualization": "7.10.0"},
    }
    resp = client.post(f"/api/saved_objects/visualization/{viz_id}", body)
    if resp["status"] not in (200, 201):
        print(f"ERROR creating viz {title!r}: {resp}", file=sys.stderr)
        sys.exit(1)
    return viz_id


def create_heading(client: OsdClient, label: str, description: str = "") -> str:
    """
    Create a Markdown visualization used as a section heading.
    description is rendered as a second line under the heading.
    Returns the saved-object id.
    """
    markdown = f"## {label}"
    if description:
        markdown += f"\n{description}"
    viz_id = str(uuid.uuid4())
    slug = label.lower().replace(" ", "_")
    vis_state = markdown_vis_state(f"_heading_{slug}", markdown)
    body = {
        "attributes": {
            "title": f"_heading_{slug}",
            "description": "",
            "visState": json.dumps(vis_state),
            "uiStateJSON": "{}",
            "version": 1,
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(
                {"query": {"query": "", "language": "kuery"}, "filter": []}
            )},
        },
        "references": [],
        "migrationVersion": {"visualization": "7.10.0"},
    }
    resp = client.post(f"/api/saved_objects/visualization/{viz_id}", body)
    if resp["status"] not in (200, 201):
        print(f"ERROR creating heading {label!r}: {resp}", file=sys.stderr)
        sys.exit(1)
    return viz_id


def add_panels_to_dashboard(
    client: OsdClient,
    dashboard_id: str,
    panels: list[dict],
) -> None:
    """
    Append new panels to an existing dashboard and PUT it back.

    Each entry in `panels` is a dict with keys:
        viz_id  (str)   — saved-object id of the visualization
        x, y, w, h (int) — grid position (grid is 48 columns wide)
        panel_index (str) — unique name for this panel, e.g. "panel_5"

    Example:
        add_panels_to_dashboard(client, DASHBOARD_ID, [
            {"viz_id": my_id, "x": 0, "y": 40, "w": 24, "h": 15, "panel_index": "panel_5"},
            {"viz_id": other_id, "x": 24, "y": 40, "w": 24, "h": 15, "panel_index": "panel_6"},
        ])
    """
    resp = client.get(f"/api/saved_objects/dashboard/{dashboard_id}")
    if resp["status"] != 200:
        print(f"ERROR fetching dashboard {dashboard_id}: {resp}", file=sys.stderr)
        sys.exit(1)

    dash = resp["body"]
    existing_panels = json.loads(dash["attributes"]["panelsJSON"])
    existing_refs = list(dash["references"])

    for p in panels:
        idx = p["panel_index"]
        existing_panels.append({
            "version": "7.10.0", "type": "visualization",
            "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": idx},
            "panelIndex": idx, "embeddableConfig": {}, "panelRefName": idx,
        })
        existing_refs.append({"id": p["viz_id"], "name": idx, "type": "visualization"})

    put_resp = client.put(
        f"/api/saved_objects/dashboard/{dashboard_id}",
        {
            "attributes": {**dash["attributes"], "panelsJSON": json.dumps(existing_panels)},
            "references": existing_refs,
        },
    )
    if put_resp["status"] not in (200, 201):
        print(f"ERROR updating dashboard {dashboard_id}: {put_resp}", file=sys.stderr)
        sys.exit(1)
