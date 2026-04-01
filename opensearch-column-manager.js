// ==UserScript==
// @name         OpenSearch - Column manager
// @namespace    http://tampermonkey.net/
// @version      1.2
// @description  Adds ←/→/× buttons to column headers and Shift+←/→/X keyboard shortcuts. Clicking the header focuses it (suppresses the EUI dropdown) so keyboard shortcuts are immediately usable.
// @author       anujbheda
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ─── Column management via URL hash ──────────────────────────────────────────

    function getColumns() {
        const m = location.hash.match(/columns:!\(([^)]*)\)/);
        if (!m || !m[1]) return [];
        return m[1].split(',').map(c => c.trim()).filter(Boolean);
    }

    function setColumns(cols) {
        location.hash = location.hash.replace(
            /columns:!\([^)]*\)/,
            `columns:!(${cols.join(',')})`
        );
    }

    // After a column operation the grid re-renders and all header DOM elements
    // are replaced. Re-focus the header for `fieldName` once it reappears so
    // EUI's arrow-key navigation continues to work.
    function refocusHeader(fieldName) {
        const selector = `[data-test-subj="dataGridHeaderCell-${fieldName}"] .euiDataGridHeaderCell__button`;
        const existing = document.querySelector(selector);
        if (existing) { existing.focus(); return; }

        const observer = new MutationObserver(() => {
            const btn = document.querySelector(selector);
            if (!btn) return;
            observer.disconnect();
            btn.focus();
        });
        observer.observe(document.body, { childList: true, subtree: true });
        setTimeout(() => observer.disconnect(), 3000);
    }

    function moveColumn(fieldName, direction) {
        const cols = getColumns();
        const idx = cols.indexOf(fieldName);
        if (idx === -1) return;
        const newIdx = direction === 'left' ? idx - 1 : idx + 1;
        if (newIdx < 0 || newIdx >= cols.length) return;
        [cols[idx], cols[newIdx]] = [cols[newIdx], cols[idx]];
        setColumns(cols);
        refocusHeader(fieldName);
    }

    function removeColumn(fieldName) {
        setColumns(getColumns().filter(c => c !== fieldName));
    }

    // ─── Button injection ────────────────────────────────────────────────────────

    const style = document.createElement('style');
    style.textContent = `
        .col-mgr-btns {
            display: inline-flex;
            align-items: center;
            gap: 2px;
            margin-left: 3px;
        }
        .col-mgr-btn {
            width: 16px; height: 16px;
            padding: 0; border: none; border-radius: 2px;
            cursor: pointer; font-size: 10px; font-weight: bold;
            line-height: 1; color: white; vertical-align: middle;
        }
        .col-mgr-btn:hover  { filter: brightness(1.2); }
        .col-mgr-btn:active { filter: brightness(0.9); }
        .col-mgr-btn-move   { background: #4c9aff; }
        .col-mgr-btn-remove { background: #ff6b6b; }
    `;
    document.head.appendChild(style);

    function fieldOf(header) {
        return (header.getAttribute('data-test-subj') || '').replace('dataGridHeaderCell-', '');
    }

    function injectButtons(header) {
        if (header.querySelector('.col-mgr-btns')) return;

        const fieldName = fieldOf(header);
        if (!fieldName || fieldName.startsWith('_') || fieldName === 'inspectCollapseColumn') return;

        const headerBtn = header.querySelector('.euiDataGridHeaderCell__button');
        if (!headerBtn) return;

        // Suppress the EUI dropdown on click — just focus the button so
        // keyboard shortcuts (Shift+←/→/X) are immediately usable.
        headerBtn.addEventListener('click', e => {
            if (e.target.closest('.col-mgr-btn')) return; // let action buttons through
            e.stopPropagation();
            e.preventDefault();
            headerBtn.focus();
        }, true); // capture phase so it runs before EUI's own handler

        // Keyboard shortcuts
        headerBtn.addEventListener('keydown', e => {
            if (!e.shiftKey) return;
            if      (e.key === 'ArrowLeft')          { e.preventDefault(); moveColumn(fieldName, 'left');  }
            else if (e.key === 'ArrowRight')          { e.preventDefault(); moveColumn(fieldName, 'right'); }
            else if (e.key.toLowerCase() === 'x')    { e.preventDefault(); removeColumn(fieldName);        }
        });

        const mkBtn = (text, cls, title, fn) => {
            const b = document.createElement('button');
            b.className = `col-mgr-btn ${cls}`;
            b.textContent = text;
            b.title = title;
            b.addEventListener('click', e => { e.stopPropagation(); e.preventDefault(); fn(); });
            return b;
        };

        const container = document.createElement('span');
        container.className = 'col-mgr-btns';
        container.appendChild(mkBtn('←', 'col-mgr-btn-move',   `Move "${fieldName}" left  (Shift+←)`, () => moveColumn(fieldName, 'left')));
        container.appendChild(mkBtn('→', 'col-mgr-btn-move',   `Move "${fieldName}" right (Shift+→)`, () => moveColumn(fieldName, 'right')));
        container.appendChild(mkBtn('×', 'col-mgr-btn-remove', `Remove "${fieldName}" (Shift+X)`,     () => removeColumn(fieldName)));

        const sortIcon = headerBtn.querySelector('.euiDataGridHeaderCell__icon');
        if (sortIcon) headerBtn.insertBefore(container, sortIcon);
        else          headerBtn.appendChild(container);
    }

    function injectAllButtons() {
        document.querySelectorAll('[data-test-subj^="dataGridHeaderCell-"]').forEach(injectButtons);
    }

    // ─── Observers ───────────────────────────────────────────────────────────────

    let injectTimer;

    const mutationObserver = new MutationObserver(mutations => {
        const hasNewHeaders = mutations.some(m =>
            Array.from(m.addedNodes).some(n =>
                n.nodeType === 1 && (
                    n.matches?.('[data-test-subj^="dataGridHeaderCell-"]') ||
                    n.querySelector?.('[data-test-subj^="dataGridHeaderCell-"]')
                )
            )
        );
        if (!hasNewHeaders) return;
        clearTimeout(injectTimer);
        injectTimer = setTimeout(injectAllButtons, 300);
    });

    // ─── Init ────────────────────────────────────────────────────────────────────

    const waitForGrid = setInterval(() => {
        if (!document.querySelector('.euiDataGrid')) return;
        clearInterval(waitForGrid);
        injectAllButtons();
        mutationObserver.observe(document.body, { childList: true, subtree: true });
    }, 500);
})();
