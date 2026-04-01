// ==UserScript==
// @name         OpenSearch - Column manager
// @namespace    http://tampermonkey.net/
// @version      1.1
// @description  Adds ←/→/× buttons (and Shift+←/→/X keyboard shortcuts) to column headers. Actions go through the native EUI dropdown so EUI manages its own state.
// @author       anujbheda
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ─── Column actions via native EUI dropdown ──────────────────────────────────
    //
    // Each button opens the column header's native dropdown and clicks the
    // matching menu item. This lets EUI manage its own state rather than us
    // reaching into the URL hash or React internals.

    async function triggerDropdownAction(fieldName, actionTexts) {
        const header = document.querySelector(`[data-test-subj="dataGridHeaderCell-${fieldName}"]`);
        if (!header) return;

        const headerBtn = header.querySelector('.euiDataGridHeaderCell__button');
        if (!headerBtn) return;

        // Open the native dropdown
        headerBtn.click();

        // Wait for the EUI popover to render
        await new Promise(r => setTimeout(r, 150));

        // Find the matching action in the now-visible popover.
        // EUI renders popovers as portals appended to <body>, so we search the
        // whole document but skip our own injected buttons and header cells.
        for (const btn of document.querySelectorAll('button')) {
            if (!btn.offsetParent) continue;                                   // not visible
            if (btn.classList.contains('col-mgr-btn')) continue;               // skip our buttons
            if (btn.closest('[data-test-subj^="dataGridHeaderCell-"]')) continue; // skip header buttons
            const text = btn.textContent.trim().toLowerCase();
            if (actionTexts.some(t => text === t.toLowerCase())) {
                btn.click();
                return;
            }
        }

        // Close the dropdown if the expected action wasn't found
        document.body.click();
        console.warn(`[column-manager] Dropdown action not found: ${actionTexts}`);
    }

    const moveLeft  = f => triggerDropdownAction(f, ['Move left']);
    const moveRight = f => triggerDropdownAction(f, ['Move right']);
    const remove    = f => triggerDropdownAction(f, ['Hide column', 'Remove column', 'Hide']);

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
        container.appendChild(mkBtn('←', 'col-mgr-btn-move',   `Move "${fieldName}" left  (Shift+←)`, () => moveLeft(fieldName)));
        container.appendChild(mkBtn('→', 'col-mgr-btn-move',   `Move "${fieldName}" right (Shift+→)`, () => moveRight(fieldName)));
        container.appendChild(mkBtn('×', 'col-mgr-btn-remove', `Remove "${fieldName}" (Shift+X)`,     () => remove(fieldName)));

        // Keyboard shortcuts when the header button has focus
        headerBtn.addEventListener('keydown', e => {
            if (!e.shiftKey) return;
            if      (e.key === 'ArrowLeft')          { e.preventDefault(); moveLeft(fieldName);  }
            else if (e.key === 'ArrowRight')          { e.preventDefault(); moveRight(fieldName); }
            else if (e.key.toLowerCase() === 'x')    { e.preventDefault(); remove(fieldName);    }
        });

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
