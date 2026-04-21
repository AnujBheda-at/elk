# Dashboards (as code)

NDJSON exports of OpenSearch Dashboards saved objects (dashboards and the
visualizations they reference), version-controlled alongside the userscripts.

## Layout

    dashboards/
    ├── bin/                         helper scripts (python3, no deps beyond stdlib)
    │   ├── osd_common.py            shared auth + HTTP client (OsdClient class)
    │   ├── osd_export.py            GET dashboard + refs → NDJSON
    │   ├── osd_import.py            POST NDJSON → _import (overwrite off by default)
    │   └── osd_diff.py              diff local NDJSON vs live env (read-only)
    ├── _reference/                  read-only dashboards we don't own; never import
    │   └── base-performance-realtime-analyzer/
    └── <dashboard-slug>/            one directory per owned dashboard
        ├── dashboard.ndjson
        └── README.md                purpose, owners, filter conventions

## Prerequisite: auth

The scripts reuse the encrypted cookie cache from the hyperbase-worktree
`opensearch_query` CLI. Log in once per env (cookies last ~24h):

    cd ~/h/source/hyperbase-worktree
    ./bin/opensearch_query --env staging login   # or --env prod / --env alpha

Then run scripts from this repo root.

## Day-to-day

Edit a dashboard in the UI, then pull the result back into git:

    python3 dashboards/bin/osd_export.py staging <dashboard-id> dashboards/<slug>/
    git -C . diff dashboards/<slug>/dashboard.ndjson   # review
    git -C . add dashboards/<slug>/ && git -C . commit

See what would change if you imported a local file to an env (read-only
preflight):

    python3 dashboards/bin/osd_diff.py staging dashboards/<slug>/dashboard.ndjson

Push a file into an env:

    python3 dashboards/bin/osd_import.py staging dashboards/<slug>/dashboard.ndjson
    # add --overwrite to replace existing objects (will clobber any live UI edits)

Selftest auth without doing anything else:

    python3 dashboards/bin/osd_common.py --selftest staging

## Index pattern

All owned dashboards reference the applogs index pattern by its saved-object
id `airtable-applogs-index`. This id is **identical across alpha, staging,
and prod** (hardcoded in `hyperbase-worktree/bin/_opensearch_query/cli.py`),
so a dashboard NDJSON exported from one env imports cleanly into any other.

## Skill

The `opensearch-dashboard-sync` Claude skill
(`.claude/skills/opensearch-dashboard-sync/`) documents the saved-objects
API's sharp edges (the `indexRefName` gotcha, stringified-JSON-in-JSON,
optimistic concurrency, the keyword-vs-text mapping requirement for terms
aggregations, permission-gate heuristics, etc.).

## What belongs here vs `_reference/`

- `dashboards/<slug>/` — we own it, edit it, sync it.
- `dashboards/_reference/<slug>/` — snapshot of someone else's dashboard,
  kept locally as a pattern library. Never runs through `osd_import`.
