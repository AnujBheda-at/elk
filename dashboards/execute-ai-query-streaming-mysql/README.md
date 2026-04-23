# SRS - MySQL Monitoring

MySQL query cost, latency, and traffic patterns for SRS routes.
Default view: `/executeAiQueryStreaming` (set in the dashboard query bar — change it to
`/executeAiQuery` or `/executeAiFieldPreviewQuery` to compare other routes without touching the vizzes).

Primary use-case: tracking the per-request overhead introduced by the forgery-check fix
(two extra reads — `selectParentWorkspaceIdsByApplicationIdAsync` + `getPermissionLevel…Async`).

Dashboard id (stable across envs): `f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78`

| Env | URL |
|-----|-----|
| staging | <https://opensearch-applogs.staging-shadowbox.cloud/_dashboards/app/dashboards#/view/f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78> |
| prod | <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78> |

## Base filter (all panels)

```
msg:"outgoing non crud log line of" AND routePattern:"/executeAiQueryStreaming"
```

SRS routes emit `outgoing non crud log line of {processType}`, not the web/API outgoing
canonical log line — these are two different log shapes with overlapping fields.

## Panels

| # | Title | Type | Key fields | Why |
|---|-------|------|------------|-----|
| 1 | Request Rate by Status Class | line (stacked) | `statusClass` (success / clientError / serverError) | Baseline traffic + error regressions |
| 2 | MySQL Queries per Request — avg + p95 | line (2 series) | `mysqlNumQueries` | Flat step-up post-deploy = forgery-fix cost; continued growth = regression |
| 3 | MySQL Duration (p50 / p95 / p99) | line (3 series) | `mysqlDurationMs` | p99 movement = slow shard or bad query plan |
| 4 | MySQL Share of Total Time | overlaid area (2 series) | `mysqlDurationMs`, `durationMs` | Rising mysql slice at flat total = regression; rising because total falls = LLM got faster |
| 5 | Queries by Shard Role | markdown note | `databaseQueriesByRegionAndDbShardRole` | See setup instructions in panel — requires scripted fields first |
| 6 | Top 20 Users by Request Volume | horizontal bar | `userId` | Identify hot integrations, abuse patterns, test accounts skewing aggregates |
| 7 | Top 20 Applications by MySQL Cost | horizontal bar | `applicationId`, `mysqlNumQueries` | Which customer apps drive query load |

### Panel 5 — unblocking the shard-role chart

`databaseQueriesByRegionAndDbShardRole` is a stringified JSON blob. Until scripted fields
`mysqlQueriesMain` and `mysqlQueriesApplicationLive` are added to the `airtable-applogs-index`
index pattern, the panel shows setup instructions instead of a chart.

## Alert candidates

Calibrate thresholds after 7 days of baseline data.

| Alert | Query | Proposed threshold |
|-------|-------|--------------------|
| MySQL query count regression | `avg(mysqlNumQueries)` over 15 m | > baseline + 50 %, sustained 30 m |
| MySQL slow tail | `percentile(mysqlDurationMs, 99)` over 5 m | > 500 ms, sustained 10 m |
| 5xx burst | `statusClass:serverError` count / total over 5 m | > 2 % |

## Saved searches (not dashboard panels)

### Forgery warnings

```
msg:"Body workspaceId did not match application's parent workspace"
```

Expected baseline: 0. Alert: count ≥ 1 per 5 m → page.
Sub-query `otherWorkspaceId` top-20 to see which clients are sending wrong IDs.

### Permission denials

```
msg:"Permission check failed for ai query streaming"
```

Group by `reason` (existing: `AI_NOT_ALLOWED`; post-deploy: also `NO_APPLICATION_ACCESS`).
7-day baseline: ~51 hits, all from `stateless-request-service-quarantine-stable-*` (expected).

## Three-route overview (extension)

Same panels with filter broadened to all three AI-query routes:

```
msg:"outgoing non crud log line of" AND (
  routePattern:"/executeAiQueryStreaming" OR
  routePattern:"/executeAiQuery" OR
  routePattern:"/executeAiFieldPreviewQuery"
)
```

Useful once the same forgery fix extends to the other two routes — add `routePattern` as a
`group` split on each panel to compare cost shifts across routes post-deploy.

## Sync commands

```bash
# First-time create (staging → verify → prod)
python3 dashboards/scripts/create_execute_ai_query_streaming_mysql.py staging
python3 dashboards/scripts/create_execute_ai_query_streaming_mysql.py prod  # after review

# Pull latest from prod into this file
python3 dashboards/scripts/osd_export.py prod \
    f3e4d5c6-b7a8-11f1-9012-ab34cd56ef78 \
    dashboards/execute-ai-query-streaming-mysql/

# Diff local vs staging before pushing
python3 dashboards/scripts/osd_diff.py staging \
    dashboards/execute-ai-query-streaming-mysql/dashboard.ndjson

# Push to staging (verify first)
python3 dashboards/scripts/osd_import.py staging \
    dashboards/execute-ai-query-streaming-mysql/dashboard.ndjson --overwrite

# Push to prod only after explicit user confirmation
python3 dashboards/scripts/osd_import.py prod \
    dashboards/execute-ai-query-streaming-mysql/dashboard.ndjson --overwrite
```
