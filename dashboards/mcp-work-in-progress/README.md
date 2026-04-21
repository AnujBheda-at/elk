# MCP (work in progress)

WIP dashboard for observing the MCP service's tool-call traffic. Currently
a single bar-chart panel of tool-call volume over time.

- Source env: **staging** (`opensearch-applogs.staging-shadowbox.cloud`)
- Dashboard id: `db007be0-3dab-11f1-83bb-619bc5d820fb`
- Live URL:
  <https://opensearch-applogs.staging-shadowbox.cloud/_dashboards/app/dashboards#/view/db007be0-3dab-11f1-83bb-619bc5d820fb>

## Panels

1. **MCP Tool Calls** — volume of MCP `tools/call` events over time.
   Filter: `processType:mcpService AND method:"tools/call"`.

## Expected query-bar usage

Type a filter into the dashboard's top query bar to scope every panel:

- `applicationId:appXXXXXXXXXXXXXX` — narrow to one base's tool-call activity
- `mcpOpenAiSubject:<subject>` — narrow to one OpenAI session
- `severityLevel:error` — only problem traffic

## Known gap: no split by `toolName`

The original intent was a stacked bar chart split by `toolName`. That is
blocked by an upstream mapping issue: `toolName` is registered as a
`text`-typed log field in
`hyperbase-worktree/client_server_shared/h/generators/log_field_definitions.tsx`
and therefore is not aggregatable.

To unblock:

1. Change that entry to
   `{name: 'toolName', type: LogFieldType.KEYWORD, isAggregatable: true}` and
   mirror the change in `log_field_definitions.yaml`.
2. Run `bazel run //client_server_shared/h:logger/generate`, commit,
   deploy.
3. Wait a few days for applogs indices to roll over — mappings only apply
   to **newly-created** indices. Historical data stays `text` forever.
4. Add a second viz to this dashboard: same filter, stacked mode, terms
   agg on `toolName` size 20.

## Sync commands

    # pull latest from staging into this file
    python3 dashboards/bin/osd_export.py staging \
        db007be0-3dab-11f1-83bb-619bc5d820fb \
        dashboards/mcp-work-in-progress/

    # preflight: diff local vs staging
    python3 dashboards/bin/osd_diff.py staging \
        dashboards/mcp-work-in-progress/dashboard.ndjson

    # push local to staging (add --overwrite to replace live UI edits)
    python3 dashboards/bin/osd_import.py staging \
        dashboards/mcp-work-in-progress/dashboard.ndjson
