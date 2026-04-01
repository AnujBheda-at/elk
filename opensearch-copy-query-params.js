// ==UserScript==
// @name         OpenSearch - Copy Query Params
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Adds a "Copy Query Params" button to the OpenSearch filter bar that copies all query parameters (DQL, filters, time range) as a JSON object
// @author       anujbheda + claude
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    const BUTTON_ID = 'copy-query-params-btn';

    function getDqlQuery() {
        const textarea = document.querySelector('[data-test-subj="queryInput"]');
        return textarea ? textarea.value.trim() : '';
    }

    function getTimeRange() {
        const prettyFormat = document.querySelector(
            '.euiSuperDatePicker__prettyFormat'
        );
        if (prettyFormat) {
            const text = prettyFormat.textContent.trim();
            // Remove "Show dates" suffix that's a nested span
            return text.replace(/Show dates$/, '').trim();
        }
        const durationEl = document.querySelector(
            '[data-test-subj="dataSharedTimefilterDuration"]'
        );
        return durationEl
            ? durationEl.getAttribute('data-shared-timefilter-duration')
            : '';
    }

    function getIndexPattern() {
        const el = document.querySelector(
            '[data-test-subj="indexPattern-switch-link"]'
        );
        if (el) {
            return el.textContent.trim();
        }
        const selectEl = document.querySelector('.index-pattern-selection');
        if (selectEl) {
            return selectEl.textContent.trim();
        }
        const comboEl = document.querySelector(
            '[data-test-subj="comboBoxSearchInput"]'
        );
        return comboEl ? comboEl.value.trim() : '';
    }

    function parseFilters() {
        const filterBadges = document.querySelectorAll(
            '[data-test-subj*="filter filter-enabled"]'
        );
        const filters = [];

        filterBadges.forEach((badge) => {
            const testSubj = badge.getAttribute('data-test-subj') || '';
            const keyMatch = testSubj.match(/filter-key-(\S+)/);
            const valueMatch = testSubj.match(/filter-value-(.+?)(?:\s+filter-|$)/);
            const negated = testSubj.includes('filter-negated');

            if (keyMatch) {
                const key = keyMatch[1];
                let value = valueMatch ? valueMatch[1].trim() : '';
                if (value.includes(', ')) {
                    value = value.split(', ');
                }

                filters.push({key, value, negated});
            }
        });

        return filters;
    }

    function buildQueryParams() {
        const query = getDqlQuery();
        const timeRange = getTimeRange();
        const indexPattern = getIndexPattern();
        const filters = parseFilters();

        const params = {};

        if (indexPattern) {
            params.index = indexPattern;
        }
        if (query) {
            params.query = query;
        }
        if (timeRange) {
            params.timeRange = timeRange;
        }
        if (filters.length > 0) {
            params.filters = filters;
        }

        return params;
    }

    function createButton() {
        const btn = document.createElement('button');
        btn.id = BUTTON_ID;
        btn.textContent = 'Copy Query Params';
        btn.style.cssText = [
            'margin-left: 4px',
            'padding: 4px 10px',
            'background: #006BB4',
            'color: white',
            'border: none',
            'border-radius: 4px',
            'cursor: pointer',
            'font-size: 12px',
            'font-family: inherit',
            'white-space: nowrap',
            'height: 24px',
            'line-height: 16px',
        ].join(';');

        btn.addEventListener('mouseenter', () => {
            btn.style.background = '#005a9e';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.background = '#006BB4';
        });

        btn.addEventListener('click', async () => {
            const params = buildQueryParams();

            try {
                await navigator.clipboard.writeText(
                    JSON.stringify(params, null, 2)
                );
                btn.textContent = 'Copied!';
                btn.style.background = '#017D73';
                setTimeout(() => {
                    btn.textContent = 'Copy Query Params';
                    btn.style.background = '#006BB4';
                }, 1500);
            } catch (_e) {
                btn.textContent = 'Copy failed';
                btn.style.background = '#BD271E';
                setTimeout(() => {
                    btn.textContent = 'Copy Query Params';
                    btn.style.background = '#006BB4';
                }, 2000);
            }
        });

        return btn;
    }

    function injectButton() {
        if (document.getElementById(BUTTON_ID)) {
            return;
        }

        const addFilterBtn = document.querySelector(
            '[data-test-subj="addFilter"]'
        );
        if (addFilterBtn) {
            const wrapper = addFilterBtn.closest('.euiFlexItem');
            if (wrapper) {
                const container = document.createElement('div');
                container.className =
                    'euiFlexItem euiFlexItem--flexGrowZero';
                container.style.display = 'flex';
                container.style.alignItems = 'center';
                container.appendChild(createButton());
                wrapper.parentNode.insertBefore(
                    container,
                    wrapper.nextSibling
                );
                return;
            }
        }

        const filterGroup = document.querySelector(
            '[data-test-subj="globalFilterGroup"]'
        );
        if (filterGroup) {
            const container = document.createElement('div');
            container.className =
                'euiFlexItem euiFlexItem--flexGrowZero';
            container.style.display = 'flex';
            container.style.alignItems = 'center';
            container.appendChild(createButton());
            filterGroup.appendChild(container);
        }
    }

    let prevTimeout;
    const observer = new MutationObserver(() => {
        if (prevTimeout) {
            clearTimeout(prevTimeout);
        }
        prevTimeout = setTimeout(injectButton, 200);
    });
    observer.observe(document.body, {subtree: true, childList: true});
})();
