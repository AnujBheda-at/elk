#!/usr/bin/env python3
"""
Import an NDJSON export file into OpenSearch Dashboards via the saved-objects
_import endpoint.

Usage:
    python3 dashboards/bin/osd_import.py <env> <ndjson-file> [--overwrite]

By default `overwrite` is off — the import will fail cleanly if any saved
object already exists with the same id. Pass `--overwrite` to replace. This is
a deliberate choice: silently clobbering a live dashboard is the fastest way
to lose a colleague's in-progress UI edits.

Example:
    python3 dashboards/bin/osd_import.py staging \\
        dashboards/mcp-work-in-progress/dashboard.ndjson

The script prints the response body so you can see per-object success/failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from osd_common import OsdClient


def import_ndjson(env: str, ndjson_path: Path, overwrite: bool) -> dict:
    client = OsdClient(env)
    data = ndjson_path.read_bytes()
    path = "/api/saved_objects/_import"
    if overwrite:
        path = f"{path}?overwrite=true"
    return client.post_multipart_ndjson(path, data)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = [a for a in argv[1:] if a.startswith("--")]
    overwrite = "--overwrite" in flags
    unknown = [f for f in flags if f not in {"--overwrite"}]
    if unknown or len(args) != 2:
        print("usage: osd_import.py <env> <ndjson-file> [--overwrite]", file=sys.stderr)
        return 2
    env, ndjson_str = args
    ndjson_path = Path(ndjson_str)
    if not ndjson_path.is_file():
        print(f"error: {ndjson_path} does not exist", file=sys.stderr)
        return 2

    r = import_ndjson(env, ndjson_path, overwrite)
    status = r.get("status")
    print(f"HTTP {status}")
    body = r.get("body") or r.get("error") or {}
    print(json.dumps(body, indent=2, sort_keys=True))
    if status != 200:
        return 1
    if not body.get("success", False):
        # Import can return 200 with success=false if per-object errors occurred
        # (e.g. conflicts when overwrite is off). Surface this as nonzero exit.
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
