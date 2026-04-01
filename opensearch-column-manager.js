// ==UserScript==
// @name         OpenSearch - Column manager
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Adds ←/→/× buttons (and Shift+←/→/X keyboard shortcuts) to column headers for quick reorder and remove. Manages columns via URL hash — no React internals. Width preservation is best-effort via ResizeObserver.
// @author       anujbheda
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ─── Column management via URL hash ────────────────────────────────────────
    //
    // OpenSearch Discover stores column config in the URL hash:
    //   #/?_g=(...)&_a=(columns:!(col1,col2,...),...)
    //
    // Updating location.hash triggers the app's hashchange listener, which
    // re-renders the grid — no React internals or Angular services needed.

    function getColumns() {
        const m = location.hash.match(/columns:!\(([^)]*)\)/);
        if (!m || !m[1]) return [];
        return m[1].split(',').map(c => c.trim()).filter(Boolean);
    }

    function setColumns(cols) {
        captureWidths(); // snapshot widths before the grid re-renders
        location.hash = location.hash.replace(
            /columns:!\([^)]*\)/,
            `columns:!(${cols.join(',')})`
        );
    }

    function moveColumn(fieldName, direction) {
        const cols = getColumns();
        const idx = cols.indexOf(fieldName);
        if (idx === -1) return;
        const newIdx = direction === 'left' ? idx - 1 : idx + 1;
        if (newIdx < 0 || newIdx >= cols.length) return;
        [cols[idx], cols[newIdx]] = [cols[newIdx], cols[idx]];
        setColumns(cols);
    }

    function removeColumn(fieldName) {
        setColumns(getColumns().filter(c => c !== fieldName));
    }

    // ─── Width tracking ─────────────────────────────────────────────────────────
    //
    // EUI DataGrid controls column widths via React state so inline style
    // overrides may be cleared on re-render. Best-effort: capture before any
    // column operation, re-apply after the grid rebuilds.

    const savedWidths = new Map();
    let applyingWidths = false;

    function captureWidths() {
        document.querySelectorAll('.euiDataGridHeaderCell[data-test-subj^="dataGridHeaderCell-"]').forEach(cell => {
            const w = cell.offsetWidth;
            if (w > 20) savedWidths.set(fieldOf(cell), w);
        });
    }

    function applyWidths() {
        if (!savedWidths.size || applyingWidths) return;
        applyingWidths = true;
        document.querySelectorAll('.euiDataGridHeaderCell[data-test-subj^="dataGridHeaderCell-"]').forEach(cell => {
            const w = savedWidths.get(fieldOf(cell));
            if (!w) return;
            cell.style.setProperty('width',     `${w}px`, 'important');
            cell.style.setProperty('min-width', `${w}px`, 'important');
            cell.style.setProperty('max-width', `${w}px`, 'important');
        });
        window.dispatchEvent(new Event('resize'));
        setTimeout(() => { applyingWidths = false; }, 500);
    }

    function setupResizeTracking() {
        const ro = new ResizeObserver(() => {
            if (!applyingWidths) captureWidths();
        });
        document.querySelectorAll('.euiDataGridHeaderCell').forEach(h => ro.observe(h));
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

        // Keyboard shortcuts when the header button has focus
        headerBtn.addEventListener('keydown', e => {
            if (!e.shiftKey) return;
            if      (e.key === 'ArrowLeft')          { e.preventDefault(); moveColumn(fieldName, 'left');  }
            else if (e.key === 'ArrowRight')          { e.preventDefault(); moveColumn(fieldName, 'right'); }
            else if (e.key.toLowerCase() === 'x')    { e.preventDefault(); removeColumn(fieldName);        }
        });

        const sortIcon = headerBtn.querySelector('.euiDataGridHeaderCell__icon');
        if (sortIcon) headerBtn.insertBefore(container, sortIcon);
        else          headerBtn.appendChild(container);
    }

    function injectAllButtons() {
        document.querySelectorAll('[data-test-subj^="dataGridHeaderCell-"]').forEach(injectButtons);
    }

    // ─── Observers ───────────────────────────────────────────────────────────────

    let injectTimer, widthTimer;

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
        clearTimeout(widthTimer);
        injectTimer = setTimeout(() => { injectAllButtons(); setupResizeTracking(); }, 300);
        widthTimer  = setTimeout(applyWidths, 600);
    });

    // ─── Init ────────────────────────────────────────────────────────────────────

    const waitForGrid = setInterval(() => {
        if (!document.querySelector('.euiDataGrid')) return;
        clearInterval(waitForGrid);

        injectAllButtons();
        captureWidths();
        setupResizeTracking();

        mutationObserver.observe(document.body, { childList: true, subtree: true });
    }, 500);
})();
