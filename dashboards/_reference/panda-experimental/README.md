# PAndA Experimental Dashboard (reference only)

**This is not an owned dashboard. Do not `osd_import` this file.**

## What it is

A production dashboard authored outside this repo, exported for use as a
**structural and stylistic reference** when authoring new dashboards.
26 visualizations (19 histogram, 6 line, 1 vega) covering PAndA
(Permissions and Access) metrics.

- Source env: **prod** (`opensearch-applogs.shadowbox.cloud`)
- Dashboard id: `ae1ecee0-bbfd-11f0-bef1-31ce933f02b6`
- Live URL:
  <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/ae1ecee0-bbfd-11f0-bef1-31ce933f02b6>

## Why it's in `_reference/`

The underscore prefix groups all dashboards that are read-only inspiration
material, kept distinct from dashboards we own and sync. Contents here are
**snapshots**: they can go stale relative to the live dashboard, and that's
fine — the point is to keep a stable local copy we can grep, diff, and mine
for layout / agg patterns.

## How to use it

Skim the NDJSON for patterns worth copying when authoring new dashboards:

- **Histogram vs line choice** — this dashboard uses histograms for volume
  counts and line charts for rate/trend views; see `visState.type`.
- **Vega usage** — one viz uses Vega for custom rendering; inspect its
  `visState.params.spec` for the full Vega spec.
- **Aggregation conventions** — look at each visualization's `visState.aggs`
  for how they scope metrics (terms size, orderBy, date histogram intervals).
- **Filter idioms** — `kibanaSavedObjectMeta.searchSourceJSON.query` on each
  viz shows the conventional KQL filter syntax.

Grep examples:

    # What viz types are used?
    jq -r 'select(.type=="visualization") | .attributes.visState | fromjson | .type' \
      dashboard.ndjson | sort | uniq -c

    # What queries are popular?
    jq -r 'select(.type=="visualization") | .attributes.kibanaSavedObjectMeta.searchSourceJSON | fromjson | .query.query' \
      dashboard.ndjson | sort | uniq -c | sort -rn | head

    # Inspect the Vega spec:
    jq -r 'select(.type=="visualization") | .attributes.visState | fromjson | select(.type=="vega") | .params.spec' \
      dashboard.ndjson

## Refreshing the snapshot

If the live dashboard evolves and you want an updated reference:

    python3 dashboards/bin/osd_export.py prod \
        ae1ecee0-bbfd-11f0-bef1-31ce933f02b6 \
        dashboards/_reference/panda-experimental/

This overwrites `dashboard.ndjson`. `git diff` will show what changed
upstream.

## Do not

- Do not run `osd_import.py` with this file as input. We do not own these
  saved objects; importing would attempt to create prod objects under our
  account and either fail or accidentally overwrite production state.
- Do not edit the NDJSON by hand expecting it to round-trip. The `osd_diff`
  tool against prod will show every hand edit as a diff, because prod is the
  source of truth for this dashboard — not this file.
