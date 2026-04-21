---
name: opensearch-dashboard-sync
description: Create, read, edit, and version-control OpenSearch Dashboards saved objects (dashboards, visualizations, searches) for the Airtable applogs cluster via the REST API. Use when authoring dashboards-as-code, committing NDJSON exports to git, diffing local files against a live environment, or scripting bulk edits to saved objects. Complements the opensearch-query skill, which is read-only over log data; this one writes dashboard state.
---

## What this skill is for

Programmatic creation and editing of OpenSearch Dashboards saved objects
(dashboards, visualizations, searches) for the Airtable applogs cluster,
kept in sync with NDJSON files in `dashboards/` in this repo.

Do **not** use this skill for log-data queries — those go through the
`opensearch-query` skill (hyperbase-worktree). This skill is about the
*dashboard layer*, not the underlying logs.

## Prerequisite: auth

All scripts reuse encrypted cookies cached by the hyperbase-worktree
`opensearch_query` CLI. Log in once per env (cookies last ~24h):

```bash
cd ~/h/source/hyperbase-worktree
./bin/opensearch_query --env <alpha|staging|prod> login
```

Then verify from this repo:

```bash
python3 dashboards/bin/osd_common.py --selftest <env>
```

A green response means cookies are live and the saved-objects API is
reachable.

## Updating an existing visualization (new session rule)

**Before mutating any existing saved object in a new session, always GET it
from prod first.** The NDJSON in git may be stale and the live object may have
drifted (UI edits, prior session changes not yet committed, etc.).

```python
# Correct pattern — pull live state, mutate, PUT back
resp = client.get(f"/api/saved_objects/visualization/{viz_id}")
attrs = resp["body"]["attributes"]
vs = json.loads(attrs["visState"])

# mutate vs as needed ...

attrs["visState"] = json.dumps(vs)
client.put(f"/api/saved_objects/visualization/{viz_id}", {
    "attributes": attrs,
    "references": [{"name": INDEX_REF_NAME, "type": "index-pattern", "id": INDEX_PATTERN_ID}],
})
```

Always use `env="prod"` as the source of truth for existing objects. After
mutating, export from prod, diff, and commit. Never reconstruct a viz from the
NDJSON alone when the intent is to update an existing one — the live object has
the authoritative state.

## Builder library (`osd_builder.py`)

For scripted dashboard creation or mutation, use `dashboards/bin/osd_builder.py`
rather than hand-rolling boilerplate. It provides agg builders, params builders,
vis state composers, and API helpers.

### Design contract — flexibility first

**Every factory function returns a plain Python dict. Mutate it freely before
passing it downstream.** There is no DSL, no builder chain, no objects — just
dicts that match the OSD wire format.

```python
from osd_builder import (
    count, avg, percentiles, date_histo, terms, filters_agg,
    line_vis_state, histogram_vis_state, horizontal_bar_vis_state,
    create_viz, create_heading, add_panels_to_dashboard,
)
from osd_common import OsdClient

client = OsdClient("staging")

# Build aggs, compose vis state, mutate as needed, then create
aggs = [count("1"), date_histo("2"), terms("3", field="applicationId", size=10)]
state = line_vis_state("Calls by app", aggs, y_title="calls")

# Want legend on left? Mutate the params dict:
state["params"]["legendPosition"] = "left"

# Want a custom label on the terms bucket?
state["aggs"][2]["params"]["customLabel"] = "App"

# Want a second split grouping? Append to aggs:
state["aggs"].append(terms("4", field="userId", size=5, schema="group"))

viz_id = create_viz(client, "Calls by app", "description", query, state)
```

### When a factory falls short

If a factory function doesn't expose something you need, pick one:

1. **Mutate the returned dict directly** — always works, no friction, right for one-off needs.
2. **Update the factory** — add the parameter properly. Preferred when the need will recur or when the mutation is subtle enough to warrant hiding behind a named parameter.

Do not work around a rigid factory with inline JSON strings or `json.loads` hacks.
Update the factory instead so the next caller benefits.

### Available factories

| Category | Functions |
| -------- | --------- |
| Agg builders | `count`, `avg`, `sum_`, `percentiles`, `date_histo`, `terms`, `filters_agg` |
| Params builders | `line_params`, `histogram_params`, `horizontal_bar_params` |
| Vis state | `line_vis_state`, `histogram_vis_state`, `horizontal_bar_vis_state`, `markdown_vis_state` |
| API helpers | `create_viz`, `create_heading`, `add_panels_to_dashboard` |

### Section headings with descriptions

Use `create_heading(client, label, description)` to add a Markdown viz as a
section header. The `description` renders as a second line. Use `##` for main
sections, `###` for sub-sections — just pass the full markdown string:

```python
# sub-heading: pass raw markdown instead of using create_heading
state = markdown_vis_state("_heading_sub", "### Sub-section title\nExplanation here.")
```

### Adding panels to an existing dashboard

`add_panels_to_dashboard(client, dashboard_id, panels)` handles the
fetch → mutate panelsJSON → PUT cycle. The grid is 48 columns wide:

```python
add_panels_to_dashboard(client, DASHBOARD_ID, [
    {"viz_id": viz_a, "x": 0,  "y": 40, "w": 24, "h": 15, "panel_index": "panel_5"},
    {"viz_id": viz_b, "x": 24, "y": 40, "w": 24, "h": 15, "panel_index": "panel_6"},
])
```

## Everyday workflow

### Export existing dashboard → local file

```bash
python3 dashboards/bin/osd_export.py <env> <dashboard-id> dashboards/<slug>/
```

Writes `dashboards/<slug>/dashboard.ndjson` with the dashboard plus every
saved object it references (visualizations, searches, index-patterns).

### Diff local file vs live environment

```bash
python3 dashboards/bin/osd_diff.py <env> dashboards/<slug>/dashboard.ndjson
```

Prints a unified diff. Read-only — safe against prod. The script parses
stringified-JSON fields (`visState`, `panelsJSON`, `searchSourceJSON`, etc.)
before diffing so output is readable, not a wall of backslash-escaped
blobs.

### Push local file → live environment

```bash
python3 dashboards/bin/osd_import.py <env> dashboards/<slug>/dashboard.ndjson
# add --overwrite to replace existing objects
```

`overwrite=false` by default — a silent clobber of a colleague's in-progress
UI edits is the single worst outcome here, so the tool makes you opt in.

### Add a new dashboard (first export)

1. Create the empty dashboard in the OSD UI (faster than scripting).
2. `osd_export` it.
3. Hand-write a `README.md` alongside the NDJSON.
4. Commit both. From then on, edits flow UI → export → git.

## Sharp edges (the reason this skill exists)

### 1. `indexRefName` must be wired inside `searchSourceJSON`

Creating a viz with just a `references` array is **not enough**. The
`attributes.kibanaSavedObjectMeta.searchSourceJSON` blob must ALSO contain
`"indexRefName": "<same name as references[n].name>"`. Otherwise the viz
loads but throws **"Trying to initialize aggs without index pattern"** at
render time.

Minimal correct shape:

```python
search_source = {
    "query": {"query": "processType:mcpService AND method:\"tools/call\"", "language": "kuery"},
    "filter": [],
    "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index",  # ← required
}

viz_body = {
    "attributes": {
        "title": "MCP Tool Calls",
        "visState": json.dumps({...}),
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(search_source)},
        # ...
    },
    "references": [{
        "name": "kibanaSavedObjectMeta.searchSourceJSON.index",  # ← must match indexRefName
        "type": "index-pattern",
        "id": "airtable-applogs-index",
    }],
}
```

Native `_import` / `_export` writes this correctly without thinking. Only
hand-rolled `POST /api/saved_objects/visualization` is susceptible.

### 2. Stringified JSON inside JSON

These saved-object attributes are **strings containing JSON**, not nested
objects:

- `attributes.visState`
- `attributes.panelsJSON`
- `attributes.optionsJSON`
- `attributes.uiStateJSON`
- `attributes.kibanaSavedObjectMeta.searchSourceJSON`

Always parse with `json.loads` before mutating, re-stringify with
`json.dumps` before PUTting. Forgetting to re-stringify silently breaks the
object without a server error.

### 3. Index-pattern ID is stable across envs

`airtable-applogs-index` is the saved-object id in alpha, staging, **and**
prod. Source: `hyperbase-worktree/bin/_opensearch_query/cli.py:234`. This
means an NDJSON exported from staging can be imported into alpha or prod
without rewriting references.

### 4. Field aggregatability precheck

Before writing a visualization that uses a terms aggregation on a field,
verify the field is `keyword`-typed AND `aggregatable: true`:

```bash
# List matching fields (the legend "k" ambiguously means keyword OR text — NOT definitive):
./bin/opensearch_query --env <env> fields <pattern>

# Definitive check via raw DSL:
./bin/opensearch_query --env <env> raw '{
  "size": 0,
  "query": {"match_all": {}},
  "aggs": {"by": {"terms": {"field": "<fieldname>", "size": 3}}}
}'
```

If the raw query returns a 400 with "Text fields are not optimised for
operations that require per-document field data", the mapping is wrong.
**Do not** try to work around it with `fielddata=true` — that's expensive
and almost never the right call. The correct fix is upstream in
`hyperbase-worktree/client_server_shared/h/generators/log_field_definitions.tsx`:
change the field from `LogFieldType.TEXT` to
`LogFieldType.KEYWORD, isAggregatable: true`. Also update
`log_field_definitions.yaml` to match, then run
`bazel run //client_server_shared/h:logger/generate`.

### 5. Mapping changes don't retro-apply

OpenSearch mappings are fixed when an index is created. A log-field type
change deploys forward only — new indices that roll over after the deploy
pick up the new mapping; historical indices keep their old mapping forever.
Expect partial / empty aggregation charts for days while old data ages out.
Plan for warm-up; no code change accelerates it.

### 6. Round-trip before every write

Always `GET → mutate → PUT`, never blind `PUT`. Saved-object PUTs only
preserve fields you supply — forgetting `kibanaSavedObjectMeta` on a PUT
silently drops the viz's filter. The `osd_common.OsdClient` wrapper
enforces nothing here; it's a discipline.

### 7. Optimistic concurrency via `version`

Every GET returns `"version": "<base64>"`. Pass it back on writes (via the
URL `?if_match=<version>` or in the PUT body, depending on the path) to
avoid clobbering a concurrent edit. For dashboard-as-code use, the more
practical habit is "always `osd_diff` before `osd_import`" so any drift
shows up before you overwrite it.

### 8. Permission-gate heuristics for Claude sessions

Claude's local safety gate is stricter on:

- `POST /api/saved_objects/_import` with files creating objects from scratch
  against shared envs (staging/prod).

Than on:

- `PUT /api/saved_objects/<type>/<id>` modifying an object the user already
  created.

When building a new dashboard programmatically, the smoothest flow is:
user creates the empty dashboard in the UI first (30 seconds, no gate),
hands over the URL, then the agent populates it via `POST visualization`
and `PUT dashboard`. Avoids re-litigating the safety block on every step.

## Endpoint / header reference

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/api/saved_objects/<type>/<id>` | fetch one |
| POST | `/api/saved_objects/<type>` | create w/ server-assigned id |
| POST | `/api/saved_objects/<type>/<id>` | create w/ explicit id (409 on conflict) |
| PUT | `/api/saved_objects/<type>/<id>` | update attributes + references |
| DELETE | `/api/saved_objects/<type>/<id>` | remove |
| GET | `/api/saved_objects/_find?type=<t>&search=<q>` | search |
| POST | `/api/saved_objects/_export` | body `{type, objects[]}`, returns NDJSON |
| POST | `/api/saved_objects/_import[?overwrite=true]` | multipart NDJSON body |

Required headers on writes: `Cookie`, `osd-xsrf: true`, and either
`Content-Type: application/json` or `multipart/form-data; boundary=...`
for `_import`. The `OsdClient` sets these automatically.

`<type>` values you'll actually use: `dashboard`, `visualization`, `search`,
`index-pattern`, `lens`, `map`.

## Reference dashboards

`dashboards/_reference/` holds snapshots of dashboards we do **not** own,
exported for inspiration only. `osd_import` is off-limits against those —
importing would try to create the objects under our account and could
either fail loudly or quietly overwrite prod state. Use `jq` to mine them
for patterns:

```bash
# What viz types does the reference use?
jq -r 'select(.type=="visualization") | .attributes.visState | fromjson | .type' \
  dashboards/_reference/<slug>/dashboard.ndjson | sort | uniq -c

# Common filter queries?
jq -r 'select(.type=="visualization") | .attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .query.query' \
  dashboards/_reference/<slug>/dashboard.ndjson | sort | uniq -c | sort -rn | head
```

## Worked example: end-to-end create-then-sync

This is what we did the first time to produce `dashboards/mcp-work-in-progress/`:

1. User created an empty dashboard in the OSD UI and shared the URL.
2. Agent `GET`ed the dashboard to confirm id + extract `version`.
3. Agent `POST /api/saved_objects/visualization` to create the viz, with
   `indexRefName` + `references` wired correctly (see sharp edge #1).
4. Agent `GET` the dashboard again, appended a panel to the parsed
   `panelsJSON`, added a matching entry to `references`, and `PUT` it back.
5. `osd_export.py staging <id> dashboards/mcp-work-in-progress/` captured
   the final state to NDJSON.
6. Commit the NDJSON + a hand-written `README.md` describing intent,
   deferred work, and filter conventions.

From that point on, the round-trip is: edit in UI → `osd_export` → review
diff → commit.

## Don't

- Don't hand-edit stringified-JSON blobs without `json.loads` →
  `json.dumps` — you will corrupt them.
- Don't `osd_import --overwrite` against prod without the user's explicit
  sign-off on the `osd_diff` output.
- Don't run `osd_import` against any file under `dashboards/_reference/`
  (see the reference-dir guidance above).
- Don't try to fix a `text`-mapped aggregation field with
  `fielddata=true`; the correct fix is upstream in
  `log_field_definitions.tsx` (see sharp edge #4).
