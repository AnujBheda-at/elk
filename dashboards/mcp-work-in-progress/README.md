# MCP (work in progress)

WIP dashboard for observing the MCP service's tool-call traffic.

| Env | Dashboard id | URL |
| --- | ------------ | --- |
| staging | `db007be0-3dab-11f1-83bb-619bc5d820fb` | <https://opensearch-applogs.staging-shadowbox.cloud/_dashboards/app/dashboards#/view/db007be0-3dab-11f1-83bb-619bc5d820fb> |
| prod | `b8e9a500-3db9-11f1-a30c-65753263afb6` | <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/b8e9a500-3db9-11f1-a30c-65753263afb6> |

Staging is the demo/iteration target. Iterate on staging first, then export
and import to prod when ready.

## Panels

1. **MCP Tool Calls** — volume of `mcp.tool.execute` events over time.
   Filter: `processType:mcpService AND eventName:"mcp.tool.execute"`.
2. **MCP Tool Call Latency (p50 / p95 / p99)** — percentile latency of tool
   executions. Filter: same as above, metric: `durationMs`.
3. **MCP Service Heap Usage (global avg)** — avg used + total heap across all
   instances. Filter: `processType:mcpService AND usedHeapSizeBytes:*`.
4. **MCP Service Heap Usage by serviceId** — same, split per instance.
5. **MCP Request Error Rate (% by statusClass)** — stacked-percentage bar of
   `/mcp` HTTP requests by `statusClass` (success / client_error / server_error).
   Filter: `processType:mcpService AND interServiceRoute:"/mcp" AND statusCode:*`.
6. **Top 10 Applications by MCP Tool Calls** — `applicationId` terms on
   `mcp.tool.execute` events.
7. **Top 10 Users by MCP Tool Calls** — `userId` terms on same.

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
