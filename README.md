# elk

A collection of Tampermonkey userscripts for tweaking the ELK/OpenSearch stack.

## Scripts

### `opensearch-copy-log-fetch-command.js`

Adds a **"Copy Log Fetch Command"** button to the OpenSearch document detail flyout. When clicked, it reads log fields (`agent.hostname`, `kubernetesClusterName`, `kubernetesPodName`, `msg`) from the open document and builds a ready-to-paste `grunt admin:log_fetch` command, then copies it to your clipboard.

**Matches:**
- `https://opensearch-applogs.shadowbox.cloud/*`
- `https://opensearch-applogs.staging-shadowbox.cloud/*`

![Copy Log Fetch Command button](assets/opensearch-copy-log-fetch-command.png)

---

### `opensearch-copy-query-params.js`

Adds a **"Copy Query Params"** button to the OpenSearch filter bar. Copies the current DQL query, time range, index pattern, and active filters as a JSON object.

**Matches:**
- `https://opensearch-applogs.shadowbox.cloud/*`
- `https://opensearch-applogs.staging-shadowbox.cloud/*`

![Copy Query Params button](assets/opensearch-copy-query-params.png)

**Example output:**
```json
{
  "query": "aggregatedSpanDurationMs.shadowboxPrivileges > 500.0",
  "timeRange": "Last 24 hours",
  "filters": [
    {
      "key": "action",
      "value": "ping",
      "negated": true
    },
    {
      "key": "applicationId",
      "value": [
        "appAL6oDwdQZtJf7B",
        "appEeYga5PYHiGnXw",
        "appdLAyjF4Fh4yXjV"
      ],
      "negated": false
    },
    {
      "key": "action",
      "value": "updatePrimitiveCell",
      "negated": false
    }
  ]
}
```

**Example output:**
```
grunt admin:log_fetch:fetchMatchingLogMessageFromHost --hostname=<hostname> --cluster=<cluster> --pod=<pod> --search='crud request log line'
```
