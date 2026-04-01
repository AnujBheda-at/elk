// ==UserScript==
// @name         OpenSearch - Field search
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Cmd+J (Mac) / Ctrl+J (Win) to search available fields and add them to the grid
// @author       anujbheda
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function() {
    'use strict';

    // ─── Column helpers (mirrors opensearch-column-manager.js) ──────────────────

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

    function addColumn(fieldName) {
        const cols = getColumns();
        if (!cols.includes(fieldName)) setColumns([...cols, fieldName]);
    }

    // ─── Field discovery ─────────────────────────────────────────────────────────
    //
    // Fields live in the sidebar as [data-test-subj="field-{name}-item"] elements.
    // We scan once per open() call and cache for the session.

    let cachedFields = null;

    function discoverFields() {
        if (cachedFields) return cachedFields;

        const fields = new Set();
        for (const el of document.querySelectorAll('[data-test-subj$="-showDetails"]')) {
            const m = el.getAttribute('data-test-subj').match(/^field-(.+)-showDetails$/);
            if (m) fields.add(m[1]);
        }

        cachedFields = [...fields].sort();
        return cachedFields;
    }

    // ─── UI ──────────────────────────────────────────────────────────────────────

    const style = document.createElement('style');
    style.textContent = `
        #fs-overlay {
            position: fixed;
            inset: 0;
            background: rgba(0,0,0,.45);
            z-index: 100000;
            display: flex;
            align-items: flex-start;
            justify-content: center;
            padding-top: 15vh;
        }
        #fs-box {
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,.24);
            width: 480px;
            max-height: 400px;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }
        #fs-input {
            padding: 14px 16px;
            font-size: 15px;
            border: none;
            border-bottom: 1px solid #e0e4e9;
            outline: none;
            width: 100%;
            box-sizing: border-box;
            flex-shrink: 0;
        }
        #fs-list {
            overflow-y: auto;
            flex: 1;
        }
        .fs-item {
            padding: 8px 16px;
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .fs-item.fs-active { background: #f0f4ff; }
        .fs-item.fs-added  { color: #a0aab4; }
        .fs-badge {
            font-size: 11px;
            color: #b0bac4;
            flex-shrink: 0;
        }
        #fs-empty {
            padding: 20px 16px;
            font-size: 13px;
            color: #a0aab4;
            text-align: center;
        }
        #fs-footer {
            padding: 5px 16px;
            font-size: 11px;
            color: #b0bac4;
            border-top: 1px solid #e0e4e9;
            flex-shrink: 0;
        }
    `;
    document.head.appendChild(style);

    let overlay, input, list;
    let activeIdx = 0;
    let visibleItems = []; // { name, added }

    function build() {
        overlay = document.createElement('div');
        overlay.id = 'fs-overlay';

        const box = document.createElement('div');
        box.id = 'fs-box';

        input = document.createElement('input');
        input.id = 'fs-input';
        input.placeholder = 'Search fields…';
        input.setAttribute('autocomplete', 'off');
        input.setAttribute('spellcheck', 'false');

        list = document.createElement('div');
        list.id = 'fs-list';

        const footer = document.createElement('div');
        footer.id = 'fs-footer';
        footer.textContent = '↑↓ navigate · Enter to add · Esc to close';

        box.append(input, list, footer);
        overlay.appendChild(box);
        document.body.appendChild(overlay);

        overlay.addEventListener('click', e => { if (e.target === overlay) close(); });
        input.addEventListener('input', render);
        input.addEventListener('keydown', onKey);
    }

    function render() {
        const q = input.value.toLowerCase();
        const addedSet = new Set(getColumns());
        const all = discoverFields();

        visibleItems = (q ? all.filter(f => f.toLowerCase().includes(q)) : all)
            .map(name => ({ name, added: addedSet.has(name) }));

        if (!visibleItems.length) {
            list.innerHTML = `<div id="fs-empty">${q ? 'No matching fields' : 'No fields found — is the sidebar open?'}</div>`;
            activeIdx = 0;
            return;
        }

        list.innerHTML = '';
        activeIdx = 0;

        visibleItems.forEach(({ name, added }, i) => {
            const el = document.createElement('div');
            el.className = 'fs-item' + (added ? ' fs-added' : '') + (i === 0 ? ' fs-active' : '');

            const nameEl = document.createElement('span');
            nameEl.textContent = name;
            el.appendChild(nameEl);

            if (added) {
                const badge = document.createElement('span');
                badge.className = 'fs-badge';
                badge.textContent = 'added';
                el.appendChild(badge);
            }

            el.addEventListener('click', () => pick(name));
            el.addEventListener('mouseenter', () => setActive(i));
            list.appendChild(el);
        });
    }

    function setActive(idx) {
        list.querySelectorAll('.fs-item').forEach((el, i) =>
            el.classList.toggle('fs-active', i === idx)
        );
        activeIdx = idx;
        list.querySelectorAll('.fs-item')[idx]?.scrollIntoView({ block: 'nearest' });
    }

    function onKey(e) {
        if      (e.key === 'ArrowDown') { e.preventDefault(); setActive(Math.min(activeIdx + 1, visibleItems.length - 1)); }
        else if (e.key === 'ArrowUp')   { e.preventDefault(); setActive(Math.max(activeIdx - 1, 0)); }
        else if (e.key === 'Enter')     { e.preventDefault(); if (visibleItems[activeIdx]) pick(visibleItems[activeIdx].name); }
        else if (e.key === 'Escape')    { e.preventDefault(); close(); }
    }

    function pick(fieldName) {
        addColumn(fieldName);
        close();
    }

    function open() {
        if (!overlay) build();
        cachedFields = null;          // refresh field list on every open
        overlay.style.display = 'flex';
        input.value = '';
        render();
        input.focus();
    }

    function close() {
        if (overlay) overlay.style.display = 'none';
    }

    // ─── Shortcut ────────────────────────────────────────────────────────────────

    document.addEventListener('keydown', e => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'j') {
            e.preventDefault();
            e.stopPropagation();
            overlay?.style.display === 'flex' ? close() : open();
        }
    }, true);
})();
