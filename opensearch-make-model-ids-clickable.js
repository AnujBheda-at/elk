// ==UserScript==
// @name         OpenSearch - Make modelIds clickable
// @namespace    http://tampermonkey.net/
// @version      0.2
// @description  Makes model IDs (trace, action, user, app, etc.) clickable links in the OpenSearch Dashboards data grid. Uses CSS styling + click delegation instead of DOM mutation to correctly handle virtual scrolling.
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

    let applicationId;

    const matchers = [
        [/^trc.{14}$/, getOpenSearchUrlBuilder('internalTraceId')],
        [/^act.{14}$/, getOpenSearchUrlBuilder('actionId')],
        [/^req.{14}$/, getOpenSearchUrlBuilder('requestId')],
        [/^pgl.{14}$/, getOpenSearchUrlBuilder('pageLoadId')],
        [/^pro.{14}$/, getOpenSearchUrlBuilder('processId')],
        [/^wkr.{14}$/, getOpenSearchUrlBuilder('serviceId')],
        [/^app.{14}$/, (app) => { applicationId = app; return getSupportPanelUrl(app); }],
        // [/^pbd.{14}$/, (pbd) => getSupportPanelUrl(applicationId + '%23' + pbd)],
        [/^usr.{14}$/, getSupportPanelUrl],
    ];

    // Style matching spans as links — no DOM mutation, no hide/show tricks.
    // This survives virtual scroll recycling because attributes are re-evaluated
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

        // Skip if we already processed this exact text on this node.
        if (span.getAttribute('data-link-text') === text) return;

        // Record that we've examined this text, regardless of match outcome.
        span.setAttribute('data-link-text', text);

        for (const [regex, getUrl] of matchers) {
            if (regex.test(text)) {
                span.setAttribute('data-link-url', getUrl(text));
                return;
            }
        }

        // No match — clear any stale link attribute from a previous value.
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
