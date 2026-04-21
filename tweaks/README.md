# Tweaks

Tampermonkey userscripts for the Airtable OpenSearch/applogs UI. Install via the Tampermonkey browser extension — paste the script content or point it at the raw GitHub URL.

All scripts match:
- `https://opensearch-applogs.shadowbox.cloud/*`
- `https://opensearch-applogs.staging-shadowbox.cloud/*`

## Scripts

| File | What it does |
|---|---|
| `opensearch-copy-log-fetch-command.js` | Adds a **Copy Log Fetch Command** button to the document detail flyout. Builds a ready-to-paste `grunt admin:log_fetch` command from the open document's hostname, cluster, pod, and message. |
| `opensearch-copy-query-params.js` | Adds a **Copy Query Params** button to the filter bar. Copies the current DQL query, time range, index pattern, and active filters as JSON. |
| `opensearch-make-model-ids-clickable.js` | Detects model ID prefixes in the data grid (`trc`, `act`, `req`, `app`, `usr`, etc.) and linkifies them — trace/request IDs open Discover filtered by that ID; app/user IDs open the support panel. |
| `opensearch-column-manager.js` | Adds **← → ×** buttons to each column header for one-click reorder and remove. Also supports `Shift+←` / `Shift+→` / `Shift+X` keyboard shortcuts when a header is focused. |
| `opensearch-field-search.js` | **Cmd+J** (Mac) / **Ctrl+J** (Win) opens a modal to search and add fields to the grid. Already-added fields show an `added` badge. |
