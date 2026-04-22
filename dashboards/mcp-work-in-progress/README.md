# MCP (work in progress)

WIP dashboard for observing the MCP service's tool-call traffic.

Same dashboard id across envs: `db007be0-3dab-11f1-83bb-619bc5d820fb`

| Env | URL |
| --- | --- |
| staging | <https://opensearch-applogs.staging-shadowbox.cloud/_dashboards/app/dashboards#/view/db007be0-3dab-11f1-83bb-619bc5d820fb> |
| prod | <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/db007be0-3dab-11f1-83bb-619bc5d820fb> |

Staging is the demo/iteration target. Iterate on staging first, then export
and import to prod when ready.

## Panels

### On-call row

| Panel | Type | Query |
|---|---|---|
| Tool Errors | metric (count) | `processType:mcpService AND msg:"MCP tool completed with error"` |
| Tool p95 Latency | metric (p95 of `durationMs`) | `processType:mcpService AND msg:"MCP tool completed" AND level:30` |
| /mcp 5xx Count | metric (count) | `processType:mcpService AND interServiceRoute:"/mcp" AND statusCode >= 500` |
| CRUD Failures | metric (count) | `isFromMcpOrigin:true AND msg:"crud request log line" AND NOT status:SUCCESS` |

### Traffic

| Panel | Type | Query |
|---|---|---|
| MCP Tool Calls (total) | metric (count) | `processType:mcpService AND msg:"MCP tool called"` |
| MCP Tool Calls | histogram over time | `processType:mcpService AND msg:"MCP tool called"` |
| MCP Tool Calls by applicationId (top 10) | horizontal bar | `processType:mcpService AND msg:"MCP tool called"` |
| MCP Tool Calls by userId (top 10) | horizontal bar | `processType:mcpService AND msg:"MCP tool called"` |
| MCP Tool Calls by userAgent (top 15) | horizontal bar | `processType:mcpService AND msg:"MCP tool called"` |
| MCP Active Sessions over Time | line (cardinality of `oauthAccessTokenId`) | `processType:mcpService AND msg:"MCP tool called"` |

### Performance

| Panel | Type | Query |
|---|---|---|
| MCP Tool Latency — Success (p50/p95/p99) | line | `processType:mcpService AND msg:"MCP tool completed" AND level:30` |
| MCP Tool Latency — Errors & Validation (p50/p95/p99) | line, split by msg type | `processType:mcpService` with filters split on `msg:"MCP tool completed with error"` and `msg:"MCP tool input validation failed"` |
| MCP CRUD Downstream Latency Breakdown | stacked histogram | `isFromMcpOrigin:true AND msg:"crud request log line"` — avg of `aggregatedSpanDurationMs.*` sub-fields |
| MCP Worker Queue Pressure (p95) | line | `isFromMcpOrigin:true AND msg:"crud request log line"` — p95 of `queueLength` and `workerChildQueueDurationMs` |
| MCP Interactive Queue Blame (p95) | line | `isFromMcpOrigin:true AND msg:"crud request log line"` — p95 of `interactiveQueueingBlameMs` and `timeBlockingAnyInteractiveRequestMs` |
| MCP Tool Call → CRUD Fan-out (fleet) | line, two series | `msg:"MCP tool called"` vs `isFromMcpOrigin:true AND msg:"crud request log line"` |

### Errors

| Panel | Type | Query |
|---|---|---|
| MCP Request Error Rate (% by statusClass) | stacked % histogram | `processType:mcpService AND interServiceRoute:"/mcp" AND statusCode >= 400` |
| MCP /mcp Errors by statusCode | stacked histogram | `processType:mcpService AND interServiceRoute:"/mcp" AND statusCode >= 400` |
| MCP CRUD Failures by modelClassName / apiName / action | data table | `msg:"crud request log line" AND isFromMcpOrigin:true AND NOT status:SUCCESS` |
| MCP CRUD Failures over Time by modelClassName / action | line, split by model+action | same as above |
| MCP CRUD Failure Status over Time | line, split by `status` | same as above |
| MCP Public API Errors by errorType (top 10) | horizontal bar | `processType:mcpService AND msg:"Public API request returned non-200"` |

## TODOs

- **Public API `toolName` context** — `public_api_fetcher.tsx` uses a fresh logger instead of the child logger from `_registerTool`, so `toolName`, `applicationId`, `userId` are absent from `"Public API request returned non-200"` logs. Fix: pass the child logger in. Once deployed, upgrade the `errorType` bar to a two-level `errorType × toolName` breakdown.
  - Manual workaround: both logs share the same `requestId` — search `requestId:<id>` in Discover to find the tool that caused a specific public API error.

- **Private API error extraction** — the `mcp_origin_crud_requester` returns non-success responses as a `{err}` Result without logging a structured error line from the MCP service side. The worker-side `crud request log line` is the closest equivalent (captured in the CRUD failures panels). Consider adding a structured log in the private requester's error path with `modelClassName`, `action`, `statusCode`, and error body, similar to what `public_api_fetcher.tsx` does.

### Infrastructure

| Panel | Type | Query |
|---|---|---|
| MCP Service Heap Usage (global avg) | line | `processType:mcpService AND usedHeapSizeBytes:*` |
| MCP Service Heap Usage by serviceId | line, split by `serviceId` | same as above |
| MCP Event Loop Utilization by serviceId | line, split by `serviceId` | same as above — avg of `eventLoopUtilization` |

## Expected query-bar usage

Type a filter into the dashboard's top query bar to scope every panel:

- `applicationId:appXXXXXXXXXXXXXX` — narrow to one base's tool-call activity
- `mcpOpenAiSubject:<subject>` — narrow to one OpenAI session
- `severityLevel:error` — only problem traffic

## Known gap: no split by `toolName`

The original intent was a stacked bar chart split by `toolName`. That is
blocked by an upstream mapping issue: `toolName` is registered as a
`text`-typed log field in
`hyperbase/client_server_shared/h/generators/log_field_definitions.tsx`
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
    python3 dashboards/scripts/osd_export.py staging \
        db007be0-3dab-11f1-83bb-619bc5d820fb \
        dashboards/mcp-work-in-progress/

    # preflight: diff local vs staging
    python3 dashboards/scripts/osd_diff.py staging \
        dashboards/mcp-work-in-progress/dashboard.ndjson

    # push local to staging (add --overwrite to replace live UI edits)
    python3 dashboards/scripts/osd_import.py staging \
        dashboards/mcp-work-in-progress/dashboard.ndjson
