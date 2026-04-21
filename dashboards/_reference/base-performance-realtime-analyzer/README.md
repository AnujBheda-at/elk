# Base Performance Realtime Analyzer (reference only)

**This is not an owned dashboard. Do not `osd_import` this file.**

## What it is

An exhaustive production dashboard authored outside this repo, exported for
use as a **structural and stylistic reference** when authoring new dashboards.
62 visualizations covering base-level performance metrics, broken down by
action, userId, queue length, and more.

- Source env: **prod** (`opensearch-applogs.shadowbox.cloud`)
- Dashboard id: `bcdf4560-56cf-11eb-adc2-5b51018bd514`
- Live URL:
  <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/bcdf4560-56cf-11eb-adc2-5b51018bd514>

## Why it's in `_reference/`

The underscore prefix groups all dashboards that are read-only inspiration
material, kept distinct from dashboards we own and sync. Contents here are
**snapshots**: they can go stale relative to the live dashboard, and that's
fine — the point is to keep a stable local copy we can grep, diff, and mine
for layout / agg patterns.

## How to use it

Skim the NDJSON for patterns worth copying when authoring new dashboards:

- **Panel layout / density** — look at `gridData` values in the dashboard's
  `panelsJSON` to see how 62 panels are arranged across the grid.
- **Aggregation conventions** — look at each visualization's `visState.aggs`
  for how they scope metrics (terms size, orderBy, missingBucket settings).
- **Filter idioms** — `kibanaSavedObjectMeta.searchSourceJSON.query` on each
  viz shows the conventional filter syntax the authors chose.
- **Color palettes / legend positions** — `visState.params` fields for axis
  styling, `legendPosition`, tooltip toggles.

Grep examples:

    # What viz types are used?
    jq -r 'select(.type=="visualization") | .attributes.visState | fromjson | .type' \
      dashboard.ndjson | sort | uniq -c

    # What queries are popular?
    jq -r 'select(.type=="visualization") | .attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .query.query' \
      dashboard.ndjson | sort | uniq -c | sort -rn | head

## Refreshing the snapshot

If the live dashboard evolves and you want an updated reference:

    python3 dashboards/bin/osd_export.py prod \
        bcdf4560-56cf-11eb-adc2-5b51018bd514 \
        dashboards/_reference/base-performance-realtime-analyzer/

This overwrites `dashboard.ndjson`. `git diff` will show what changed
upstream.

## Do not

- Do not run `osd_import.py` with this file as input. We do not own these
  saved objects; importing would attempt to create prod objects under our
  account and either fail or accidentally overwrite production state.
- Do not edit the NDJSON by hand expecting it to round-trip. The `osd_diff`
  tool against prod will show every hand edit as a diff, because prod is the
  source of truth for this dashboard — not this file.
