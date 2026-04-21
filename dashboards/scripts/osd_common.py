#!/usr/bin/env python3
"""
Shared HTTP client for the OpenSearch Dashboards saved-objects API.

Auth is reused from the hyperbase-worktree opensearch_query CLI — this module
does not re-implement Chrome cookie extraction. To get a fresh session:

    cd ~/h/source/hyperbase-worktree
    ./bin/opensearch_query --env <alpha|staging|prod> login

Cookies live at ~/.opensearch_cookies_<env>.enc and expire in ~24h.

Usage:
    from osd_common import OsdClient

    client = OsdClient("staging")
    r = client.get("/api/saved_objects/dashboard/<id>")
    assert r["status"] == 200
    print(r["body"]["attributes"]["title"])

CLI selftest:
    python3 dashboards/bin/osd_common.py --selftest staging
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

HYPERBASE_BIN = Path.home() / "h" / "source" / "hyperbase" / "bin"
sys.path.insert(0, str(HYPERBASE_BIN))
from _shared_chrome_auth import load_cookies  # noqa: E402

ENVIRONMENTS = {
    "alpha": "opensearch-applogs.alpha-shadowbox.cloud",
    "staging": "opensearch-applogs.staging-shadowbox.cloud",
    "prod": "opensearch-applogs.shadowbox.cloud",
}
KEYCHAIN_SERVICE = "opensearch_query_key"
DASHBOARDS_PREFIX = "/_dashboards"
SAVED_OBJECTS_INDEX_PATTERN_ID = "airtable-applogs-index"


class OsdClient:
    def __init__(self, env: str) -> None:
        if env not in ENVIRONMENTS:
            raise ValueError(f"unknown env {env!r}; valid: {sorted(ENVIRONMENTS)}")
        self.env = env
        self.host = ENVIRONMENTS[env]
        normalized = "prod" if env == "production" else env
        cookie_file = Path.home() / f".opensearch_cookies_{normalized}.enc"
        self._credentials = load_cookies(cookie_file, KEYCHAIN_SERVICE)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        if not path.startswith(DASHBOARDS_PREFIX):
            path = DASHBOARDS_PREFIX + path
        return f"https://{self.host}{path}"

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        raw_body: bytes | None = None,
        content_type: str = "application/json",
    ) -> dict:
        url = self._url(path)
        if raw_body is not None:
            data = raw_body
        elif body is not None:
            data = json.dumps(body).encode()
        else:
            data = None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Cookie", self._credentials.cookies)
        req.add_header("osd-xsrf", "true")
        if data is not None:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return {
                    "status": resp.status,
                    "body": json.loads(raw) if raw else {},
                }
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                parsed = {"raw": raw}
            return {"status": e.code, "error": parsed}

    def get(self, path: str) -> dict:
        return self._request("GET", path)

    def post(self, path: str, body: dict) -> dict:
        return self._request("POST", path, body=body)

    def put(self, path: str, body: dict) -> dict:
        return self._request("PUT", path, body=body)

    def delete(self, path: str) -> dict:
        return self._request("DELETE", path)

    def post_multipart_ndjson(self, path: str, ndjson_bytes: bytes) -> dict:
        boundary = f"----osd{uuid.uuid4().hex}"
        parts = [
            f"--{boundary}".encode(),
            b'Content-Disposition: form-data; name="file"; filename="upload.ndjson"',
            b"Content-Type: application/ndjson",
            b"",
            ndjson_bytes,
            f"--{boundary}--".encode(),
            b"",
        ]
        raw = b"\r\n".join(parts)
        return self._request(
            "POST", path, raw_body=raw,
            content_type=f"multipart/form-data; boundary={boundary}",
        )


def selftest(env: str) -> int:
    client = OsdClient(env)
    r = client.get("/api/status")
    if r.get("status") == 200:
        overall = r["body"].get("status", {}).get("overall", {})
        print(f"ok   env={env}  overall={overall.get('state')!r}  level={overall.get('level')!r}")
        return 0
    print(f"fail env={env}  status={r.get('status')}  error={r.get('error')}")
    return 1


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "--selftest":
        return selftest(argv[2])
    print(
        "osd_common.py — shared HTTP client; import OsdClient from it.\n"
        "  python3 osd_common.py --selftest <alpha|staging|prod>",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
