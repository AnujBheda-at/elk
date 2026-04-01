// ==UserScript==
// @name         OpenSearch - Copy Log Fetch Command
// @namespace    http://tampermonkey.net/
// @version      0.1
// @description  Adds a "Copy Log Fetch Command" button to the OpenSearch document detail flyout that generates a grunt admin:log_fetch command
// @author       anujbheda + claude
// @match        https://opensearch-applogs.shadowbox.cloud/*
// @match        https://opensearch-applogs.staging-shadowbox.cloud/*
// @grant        none
// ==/UserScript==

(function () {
    'use strict';

    const BUTTON_ID = 'copy-log-fetch-command-btn';

    function getFieldValue(fieldName) {
        const el = document.querySelector(`[data-test-subj="tableDocViewRow-${fieldName}-value"]`);
        return el ? el.textContent.trim() : null;
    }

    function buildCommand() {
        const hostname = getFieldValue('agent.hostname') || getFieldValue('host.hostname');
        if (!hostname) {
            return null;
        }

        const cluster = getFieldValue('kubernetesClusterName');
        const pod = getFieldValue('kubernetesPodName');
        const msg = getFieldValue('msg');

        if (!msg) {
            return null;
        }

        let cmd = `grunt admin:log_fetch:fetchMatchingLogMessageFromHost --hostname=${hostname}`;

        if (cluster) {
            cmd += ` --cluster=${cluster}`;
        }

        if (pod) {
            cmd += ` --pod=${pod}`;
        }

        if (msg) {
            cmd += ` --search='${msg}'`;
        }

        return cmd;
    }

    function createButton() {
        const btn = document.createElement('button');
        btn.id = BUTTON_ID;
        btn.textContent = 'Copy Log Fetch Command';
        btn.style.cssText = [
            'margin: 8px 0',
            'padding: 6px 12px',
            'background: #006BB4',
            'color: white',
            'border: none',
            'border-radius: 4px',
            'cursor: pointer',
            'font-size: 14px',
            'font-family: inherit',
        ].join(';');

        btn.addEventListener('mouseenter', () => {
            btn.style.background = '#005a9e';
        });
        btn.addEventListener('mouseleave', () => {
            btn.style.background = '#006BB4';
        });

        btn.addEventListener('click', async () => {
            const cmd = buildCommand();
            if (!cmd) {
                btn.textContent = 'Missing hostname or search fields';
                btn.style.background = '#BD271E';
                setTimeout(() => {
                    btn.textContent = 'Copy Log Fetch Command';
                    btn.style.background = '#006BB4';
                }, 2000);
                return;
            }

            try {
                await navigator.clipboard.writeText(cmd);
                btn.textContent = 'Copied!';
                btn.style.background = '#017D73';
                setTimeout(() => {
                    btn.textContent = 'Copy Log Fetch Command';
                    btn.style.background = '#006BB4';
                }, 1500);
            } catch (_e) {
                btn.textContent = 'Copy failed';
                btn.style.background = '#BD271E';
                setTimeout(() => {
                    btn.textContent = 'Copy Log Fetch Command';
                    btn.style.background = '#006BB4';
                }, 2000);
            }
        });

        return btn;
    }

    function injectButton() {
        const flyout = document.querySelector('[data-test-subj="documentDetailFlyOut"]');
        if (!flyout) {
            return;
        }

        if (flyout.querySelector(`#${BUTTON_ID}`)) {
            return;
        }

        const overflowContent = flyout.querySelector('.euiFlyoutBody__overflowContent');
        if (!overflowContent) {
            return;
        }

        const btn = createButton();
        overflowContent.insertBefore(btn, overflowContent.firstChild);
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
