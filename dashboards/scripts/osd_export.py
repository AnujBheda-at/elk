#!/usr/bin/env python3
"""
Export an OpenSearch Dashboards dashboard and every saved object it references
to a single NDJSON file on disk. Output format matches the native OSD export:
one JSON object per line, plus a trailing summary line.

Output is deterministic — the same dashboard state always yields byte-identical
NDJSON, so `git diff` between exports is meaningful.

Usage:
    python3 dashboards/bin/osd_export.py <env> <dashboard-id> <out-dir>

Example:
    python3 dashboards/bin/osd_export.py staging \\
        db007be0-3dab-11f1-83bb-619bc5d820fb \\
        dashboards/mcp-work-in-progress/

Writes <out-dir>/dashboard.ndjson.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from osd_common import OsdClient


REFERENCE_SAVED_OBJECT_TYPES = {"visualization", "search", "index-pattern", "lens", "map"}


def _canonicalize(obj: dict) -> dict:
    """Produce a deterministic dict ordering for idempotent NDJSON output.

    OpenSearch's GET response includes volatile top-level fields like
    `updated_at` and `namespaces` that vary between calls. Strip them — we
    version-control the content, not the sync metadata.
    """
    drop_top_level = {"updated_at", "namespaces", "coreMigrationVersion"}
    out = {k: v for k, v in obj.items() if k not in drop_top_level}
    return out


def export_dashboard(env: str, dashboard_id: str, out_dir: Path) -> Path:
    client = OsdClient(env)

    dash_resp = client.get(f"/api/saved_objects/dashboard/{dashboard_id}")
    if dash_resp.get("status") != 200:
        raise SystemExit(
            f"failed to GET dashboard {dashboard_id} from {env}: "
            f"status={dash_resp.get('status')} error={dash_resp.get('error')}"
        )
    dashboard = dash_resp["body"]

    # Collect all objects we want to export, deduplicated by (type, id).
    exported: dict[tuple[str, str], dict] = {}
    exported[(dashboard["type"], dashboard["id"])] = dashboard

    for ref in dashboard.get("references", []):
        t = ref.get("type")
        i = ref.get("id")
        if not t or not i or t not in REFERENCE_SAVED_OBJECT_TYPES:
            continue
        key = (t, i)
        if key in exported:
            continue
        r = client.get(f"/api/saved_objects/{t}/{i}")
        if r.get("status") != 200:
            print(
                f"warning: failed to GET {t}/{i}: "
                f"status={r.get('status')} error={r.get('error')}",
                file=sys.stderr,
            )
            continue
        exported[key] = r["body"]

    # Deterministic ordering: sort by (type, id). Summary last.
    ordered_keys = sorted(exported.keys())

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "dashboard.ndjson"
    with out_path.open("w") as f:
        for key in ordered_keys:
            obj = _canonicalize(exported[key])
            f.write(json.dumps(obj, sort_keys=True) + "\n")
        summary = {
            "exportedCount": len(exported),
            "missingRefCount": 0,
            "excludedObjects": [],
            "excludedObjectsCount": 0,
            "missingReferences": [],
        }
        f.write(json.dumps(summary, sort_keys=True) + "\n")
    return out_path


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print("usage: osd_export.py <env> <dashboard-id> <out-dir>", file=sys.stderr)
        return 2
    env, dashboard_id, out_dir_str = argv[1], argv[2], argv[3]
    out_dir = Path(out_dir_str)
    out_path = export_dashboard(env, dashboard_id, out_dir)
    # Count lines (objects + summary).
    with out_path.open() as f:
        lines = sum(1 for _ in f)
    print(f"wrote {out_path} ({lines} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
