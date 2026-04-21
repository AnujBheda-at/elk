#!/usr/bin/env python3
"""
Diff a local NDJSON export file against the live saved objects in an
OpenSearch Dashboards environment.

For each saved object in the file, GETs the live version and prints a
unified diff. Stringified-JSON-in-JSON fields (visState, panelsJSON,
optionsJSON, searchSourceJSON, uiStateJSON) are parsed before diffing so
differences are readable.

Read-only. Useful before running an import to see what would change.

Usage:
    python3 dashboards/bin/osd_diff.py <env> <ndjson-file>

Exit codes:
    0 — no differences
    1 — differences found (or missing objects)
    2 — usage error
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from osd_common import OsdClient


STRINGIFIED_JSON_PATHS = (
    ("attributes", "visState"),
    ("attributes", "panelsJSON"),
    ("attributes", "optionsJSON"),
    ("attributes", "uiStateJSON"),
    ("attributes", "kibanaSavedObjectMeta", "searchSourceJSON"),
)

DROP_TOP_LEVEL = {"updated_at", "namespaces", "coreMigrationVersion"}


def _parse_stringified(obj: dict) -> dict:
    """Parse known stringified-JSON fields in place for readable diffs."""
    out = json.loads(json.dumps(obj))  # deep copy
    for path in STRINGIFIED_JSON_PATHS:
        cur = out
        for part in path[:-1]:
            if not isinstance(cur, dict) or part not in cur:
                cur = None
                break
            cur = cur[part]
        if not isinstance(cur, dict):
            continue
        leaf = path[-1]
        raw = cur.get(leaf)
        if isinstance(raw, str):
            try:
                cur[leaf] = json.loads(raw)
            except json.JSONDecodeError:
                pass  # leave the raw string if not valid JSON
    return out


def _canonicalize(obj: dict) -> dict:
    return {k: v for k, v in obj.items() if k not in DROP_TOP_LEVEL}


def _pretty(obj: dict) -> list[str]:
    return json.dumps(_parse_stringified(_canonicalize(obj)), indent=2, sort_keys=True).splitlines()


def diff_file(env: str, ndjson_path: Path) -> int:
    client = OsdClient(env)
    diff_count = 0
    checked = 0
    missing = 0

    for line_num, raw in enumerate(ndjson_path.read_text().splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        obj = json.loads(raw)
        if "exportedCount" in obj:
            continue  # skip summary line
        t = obj.get("type")
        i = obj.get("id")
        if not t or not i:
            continue
        checked += 1

        r = client.get(f"/api/saved_objects/{t}/{i}")
        if r.get("status") == 404:
            print(f"- missing on {env}: {t}/{i} (line {line_num})")
            missing += 1
            diff_count += 1
            continue
        if r.get("status") != 200:
            print(
                f"! error fetching {t}/{i}: "
                f"status={r.get('status')} error={r.get('error')}"
            )
            diff_count += 1
            continue

        local = _pretty(obj)
        live = _pretty(r["body"])
        if local == live:
            continue
        diff_count += 1
        label_local = f"local:{ndjson_path}:{t}/{i}"
        label_live = f"live:{env}:{t}/{i}"
        for line in difflib.unified_diff(live, local, fromfile=label_live, tofile=label_local, lineterm=""):
            print(line)

    print(
        f"\nsummary: {checked} object(s) checked, "
        f"{diff_count} with differences, {missing} missing on {env}"
    )
    return 0 if diff_count == 0 else 1


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print("usage: osd_diff.py <env> <ndjson-file>", file=sys.stderr)
        return 2
    env, ndjson_str = argv[1], argv[2]
    ndjson_path = Path(ndjson_str)
    if not ndjson_path.is_file():
        print(f"error: {ndjson_path} does not exist", file=sys.stderr)
        return 2
    return diff_file(env, ndjson_path)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
