# SRS

General-purpose monitoring for SRS (Stateless Request Service) routes.
Covers request volume, end-to-end latency, error rates, and MySQL cost.

Default view: **all SRS routes**. Narrow to a specific route by adding a filter in the
query bar, e.g. `routePattern:"/executeAiQueryStreaming"`.

Dashboard id (stable across envs): `e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78`

| Env | URL |
|-----|-----|
| staging | <https://opensearch-applogs.staging-shadowbox.cloud/_dashboards/app/dashboards#/view/e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78> |
| prod | <https://opensearch-applogs.shadowbox.cloud/_dashboards/app/dashboards#/view/e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78> |

## Base filter (all panels)

```
msg:"outgoing non crud log line of"
```

SRS routes emit `outgoing non crud log line of {processType}`, not the web/API
outgoing canonical log line — these are two different log shapes.

## Sections

### Volume

| Panel | Type | Key fields |
|-------|------|------------|
| Request Rate by Status Class | line (stacked) | `statusClass` |
| Top 20 Routes by Volume | horizontal bar | `routePattern` |
| Top 20 Users by Volume | horizontal bar | `userId` |

### Perf

| Panel | Type | Key fields |
|-------|------|------------|
| Request Latency (p50 / p95 / p99) | line | `durationMs` |
| Top 20 Routes by Avg Duration | horizontal bar | `routePattern`, `durationMs` |

### Errors

| Panel | Type | Key fields |
|-------|------|------------|
| Server Errors Over Time | line | `statusClass:serverError` count |
| Request Status Breakdown (%) | histogram (stacked 100%) | `statusClass` |

### MySQL

| Panel | Type | Key fields |
|-------|------|------------|
| MySQL Queries per Request — avg + p95 | line | `mysqlNumQueries` |
| MySQL Duration (p50 / p95 / p99) | line | `mysqlDurationMs` |
| MySQL Share of Total Request Time | overlaid area | `mysqlDurationMs`, `durationMs` |
| Queries by Shard Role | markdown note | see setup instructions in panel |
| Top 20 Applications by MySQL Cost | horizontal bar | `applicationId`, `mysqlNumQueries` |

## Sync commands

```bash
# First-time create (staging → verify → prod)
python3 dashboards/scripts/create_srs_general.py staging
python3 dashboards/scripts/create_srs_general.py prod  # after review

# Pull latest from prod
python3 dashboards/scripts/osd_export.py prod \
    e1a2b3c4-d5e6-11f1-9012-ab34cd56ef78 \
    dashboards/srs-general/

# Diff local vs staging
python3 dashboards/scripts/osd_diff.py staging \
    dashboards/srs-general/dashboard.ndjson

# Push to staging
python3 dashboards/scripts/osd_import.py staging \
    dashboards/srs-general/dashboard.ndjson --overwrite

# Push to prod (after explicit user confirmation only)
python3 dashboards/scripts/osd_import.py prod \
    dashboards/srs-general/dashboard.ndjson --overwrite
```
