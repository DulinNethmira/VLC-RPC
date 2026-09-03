with open("web/script.js", "a", encoding="utf-8") as f:
    f.write("""

/* Diagnostics Center Logic */
let lastDiagnosticsState = null;

async function updateDiagnostics() {
    if (!window.pywebview || !window.pywebview.api) return;
    
    // Only fetch if the tab is visible
    const diagTab = document.getElementById('tab-diagnostics');
    if (!diagTab || !diagTab.classList.contains('active')) return;
    
    try {
        const data = await window.pywebview.api.get_diagnostics();
        if (!data || !data.components) return;
        
        lastDiagnosticsState = data;
        renderDiagnosticsGrid(data.components);
        renderDiagnosticsTimeline(data.timeline);
        renderDiagnosticsErrors(data.errors);
    } catch (e) {
        console.error("Failed to fetch diagnostics:", e);
    }
}

function formatRelativeTime(timestamp) {
    if (!timestamp) return "Never";
    const seconds = Math.floor(Date.now() / 1000 - timestamp);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return Math.floor(seconds / 60) + "m ago";
    if (seconds < 86400) return Math.floor(seconds / 3600) + "h ago";
    return Math.floor(seconds / 86400) + "d ago";
}

function formatTime(timestamp) {
    const d = new Date(timestamp * 1000);
    return d.toTimeString().split(' ')[0]; // HH:MM:SS
}

function renderDiagnosticsGrid(components) {
    const grid = document.getElementById('diagnostics-components-grid');
    if (!grid) return;
    
    let html = '';
    
    const icons = {
        'vlc': 'fa-play-circle',
        'discord': 'fa-discord',
        'anilist': 'fa-list',
        'metadata': 'fa-tags',
        'gemini': 'fa-brain',
        'cache': 'fa-database',
        'artwork': 'fa-image',
        'database': 'fa-server'
    };
    
    const displayNames = {
        'vlc': 'VLC Media Player',
        'discord': 'Discord RPC',
        'anilist': 'AniList Sync',
        'metadata': 'Metadata Engine',
        'gemini': 'Gemini AI',
        'cache': 'Local Cache',
        'artwork': 'Artwork Provider',
        'database': 'History Database'
    };
    
    for (const [key, comp] of Object.entries(components)) {
        const icon = icons[key] || 'fa-microchip';
        const name = displayNames[key] || key;
        
        let pendingHtml = '';
        if (comp.pending > 0) {
            pendingHtml = `<div style="margin-top: 8px; font-size: 0.75rem; color: var(--color-primary);"><i class="fas fa-spinner fa-spin"></i> ${comp.pending} pending operations</div>`;
        }
        
        html += `
            <div class="diagnostics-card">
                <div class="diag-header">
                    <span><i class="fas ${icon} fa-fw" style="margin-right: 6px; color: var(--text-secondary);"></i> ${name}</span>
                    <span class="diag-status ${comp.state}">
                        <div class="dot" style="background: currentColor; width: 6px; height: 6px; margin:0; animation:none;"></div>
                        ${comp.state}
                    </span>
                </div>
                <div class="diag-details">
                    <div>Last Success: <span style="color: var(--text-primary);">${formatRelativeTime(comp.last_success)}</span></div>
                    ${comp.last_failure ? `<div>Last Error: <span style="color: #ff5c5c;">${formatRelativeTime(comp.last_failure)}</span></div>` : ''}
                    <div class="diag-event" title="${comp.last_event}">${comp.last_event || 'No events yet'}</div>
                </div>
                ${pendingHtml}
            </div>
        `;
    }
    
    grid.innerHTML = html;
}

function renderDiagnosticsTimeline(timeline) {
    const container = document.getElementById('diagnostics-timeline');
    if (!container) return;
    
    if (!timeline || timeline.length === 0) {
        container.innerHTML = '<div style="color: var(--text-secondary); font-style: italic;">No events recorded yet.</div>';
        return;
    }
    
    // Sort descending
    const sorted = [...timeline].sort((a, b) => b.timestamp - a.timestamp);
    
    let html = '';
    for (const event of sorted) {
        html += `
            <div class="timeline-item">
                <div class="timeline-time">${formatTime(event.timestamp)} <span style="opacity:0.5; margin-left: 4px;">[${event.component}]</span></div>
                <div>${event.message}</div>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

function renderDiagnosticsErrors(errors) {
    const container = document.getElementById('diagnostics-errors');
    if (!container) return;
    
    if (!errors || errors.length === 0) {
        container.innerHTML = '<div style="color: #34d399; font-style: italic;"><i class="fas fa-check-circle"></i> No errors recorded.</div>';
        return;
    }
    
    let html = '';
    for (const err of errors) {
        const countBadge = err.count > 1 ? `<span class="error-count">${err.count}x</span>` : '';
        html += `
            <div class="error-item">
                <div class="error-header">
                    <span class="error-type">[${err.component.toUpperCase()}] ${err.type}</span>
                    <div style="display:flex; gap: 8px; align-items:center;">
                        ${countBadge}
                        <span style="font-size: 0.7rem; color: var(--text-secondary);">${formatRelativeTime(err.last_seen)}</span>
                    </div>
                </div>
                <div style="color: var(--text-primary); margin-bottom: 4px;">${err.message}</div>
                ${err.traceback ? `<details style="margin-top: 8px;"><summary style="cursor:pointer; color: var(--text-secondary); font-size: 0.75rem;">Show Stack Trace</summary><pre style="background: rgba(0,0,0,0.3); padding: 8px; border-radius: 4px; overflow-x: auto; font-size: 0.7rem; margin-top: 4px; color: #a1a1aa;">${err.traceback}</pre></details>` : ''}
            </div>
        `;
    }
    
    container.innerHTML = html;
}

async function runDiagnostics() {
    const btn = document.getElementById('btn-run-diagnostics');
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Running...';
        btn.disabled = true;
    }
    
    try {
        await window.pywebview.api.run_diagnostics();
        // Wait a few seconds for background tests to finish before allowing it again
        setTimeout(() => {
            if (btn) {
                btn.innerHTML = '<i class="fas fa-stethoscope"></i> Run Diagnostics';
                btn.disabled = false;
            }
            updateDiagnostics();
        }, 3000);
    } catch (e) {
        console.error(e);
        if (btn) {
            btn.innerHTML = '<i class="fas fa-stethoscope"></i> Run Diagnostics';
            btn.disabled = false;
        }
    }
}

async function exportDiagnostics() {
    const btn = document.getElementById('btn-export-diagnostics');
    if (btn) {
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Exporting...';
        btn.disabled = true;
    }
    
    try {
        const filepath = await window.pywebview.api.export_diagnostics();
        if (filepath) {
            addLog(`Diagnostics exported to ${filepath}`);
            // Also show a toast if available
            if (window.showToast) {
                window.showToast('Diagnostics Exported', `Saved to ${filepath}`, 'success');
            }
        }
    } catch (e) {
        console.error(e);
    } finally {
        if (btn) {
            btn.innerHTML = '<i class="fas fa-download"></i> Export Diagnostics';
            btn.disabled = false;
        }
    }
}

// Ensure updateDiagnostics runs periodically when the tab is open
setInterval(updateDiagnostics, 1000);

""")
