// ==UserScript==
// @name         OpenSearch - Make modelIds clickable
// @namespace    http://tampermonkey.net/
// @version      0.3
// @description  Makes model IDs (trace, action, user, app, pbd, pag, etc.) clickable links in the OpenSearch Dashboards data grid. Uses CSS styling + click delegation instead of DOM mutation to correctly handle virtual scrolling.
// @author       anujbheda
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';

    const BASE_URL = window.location.href.includes('staging')
        ? 'https://opensearch-applogs.staging-shadowbox.cloud'
        : 'https://opensearch-applogs.shadowbox.cloud';
    const COLUMNS = 'applicationId,action,msg,err.message,durationMs,userId,processId,processType,threadType';

    function getOpenSearchUrlBuilder(key) {
        return function(value) {
            return `${BASE_URL}/_dashboards/app/discover?security_tenant=global#/?_g=(filters:!(),refreshInterval:(pause:!t,value:0),time:(from:now-24h,to:now))&_a=(columns:!(${COLUMNS}),filters:!(('$state':(store:appState),meta:(alias:!n,disabled:!f,index:airtable-applogs-index,key:${key},negate:!f,params:(query:${value}),type:phrase),query:(match_phrase:(${key}:${value})))),index:airtable-applogs-index,interval:auto,query:(language:kuery,query:''),sort:!())`;
        };
    }

    function getSupportPanelUrl(query) {
        return `https://airtable.com/supportpanel_SLfUdGBZiJ4Oee?query=${query}`;
    }

    // Find the applicationId for the row that contains the given span.
    //
    // EUI DataGrid positions cells with `style="... top: Npx ..."`. All cells
    // in the same logical row share the same top value, so we use that to find
    // sibling cells and scan them for an app... ID.
    //
    // Returns null if applicationId is not in the currently visible columns.
    function getApplicationIdForRow(span) {
        let cell = span;
        while (cell && !cell.classList.contains('euiDataGridRowCell')) {
            cell = cell.parentElement;
        }
        if (!cell) return null;

        const top = cell.style.top;
        if (!top) return null;

        for (const otherCell of document.querySelectorAll('.euiDataGridRowCell')) {
            if (otherCell === cell || otherCell.style.top !== top) continue;
            for (const s of otherCell.querySelectorAll('span')) {
                const text = s.textContent.trim();
                if (/^app.{14}$/.test(text)) return text;
            }
        }
        return null;
    }

    function buildPageUrl(id, span) {
        const appId = getApplicationIdForRow(span);
        if (!appId) return null; // applicationId not visible — will retry on next grid update
        return getSupportPanelUrl(`${appId}%23${id}`);
    }

    const matchers = [
        [/^trc.{14}$/, (v)       => getOpenSearchUrlBuilder('internalTraceId')(v)],
        [/^act.{14}$/, (v)       => getOpenSearchUrlBuilder('actionId')(v)],
        [/^req.{14}$/, (v)       => getOpenSearchUrlBuilder('requestId')(v)],
        [/^pgl.{14}$/, (v)       => getOpenSearchUrlBuilder('pageLoadId')(v)],
        [/^pro.{14}$/, (v)       => getOpenSearchUrlBuilder('processId')(v)],
        [/^wkr.{14}$/, (v)       => getOpenSearchUrlBuilder('serviceId')(v)],
        [/^app.{14}$/, (v)       => getSupportPanelUrl(v)],
        [/^usr.{14}$/, (v)       => getSupportPanelUrl(v)],
        [/^pbd.{14}$/, (v, span) => buildPageUrl(v, span)],
        [/^pag.{14}$/, (v, span) => buildPageUrl(v, span)],
    ];

    // Style matching spans as links — no DOM mutation, no hide/show tricks.
    // Survives virtual scroll recycling because attributes are re-evaluated
    // whenever textContent changes.
    const style = document.createElement('style');
    style.textContent = `
        span[data-link-url] {
            color: #006BB4 !important;
            text-decoration: underline !important;
            cursor: pointer !important;
        }
    `;
    document.head.appendChild(style);

    // Single delegated click handler for all linkified spans.
    document.addEventListener('click', (e) => {
        const span = e.target.closest('span[data-link-url]');
        if (!span) return;
        e.preventDefault();
        e.stopPropagation();
        window.open(span.getAttribute('data-link-url'), '_blank');
    });

    function processSpan(span) {
        const text = span.textContent.trim();

        // Skip if already resolved with a URL for this exact text.
        if (span.getAttribute('data-link-text') === text && span.hasAttribute('data-link-url')) return;

        for (const [regex, getUrl] of matchers) {
            if (!regex.test(text)) continue;

            const url = getUrl(text, span);
            if (url) {
                span.setAttribute('data-link-url', url);
                span.setAttribute('data-link-text', text); // mark as fully resolved
            }
            // If url is null (e.g. applicationId not visible yet), don't mark as done
            // so we retry on the next linkifyGrid() call.
            return;
        }

        // No match — mark as done and clear any stale URL.
        span.setAttribute('data-link-text', text);
        span.removeAttribute('data-link-url');
    }

    function linkifyGrid() {
        for (const span of document.querySelectorAll(
            '.osdDocTableCell__dataField span, .euiDataGridRowCell span'
        )) {
            processSpan(span);
        }
    }

    let prevTimeout;
    const observer = new MutationObserver(() => {
        if (prevTimeout) clearTimeout(prevTimeout);
        prevTimeout = setTimeout(linkifyGrid, 200);
    });
    observer.observe(document.body, { subtree: true, childList: true });
})();
