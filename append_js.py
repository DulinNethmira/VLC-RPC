import os

js_code = """
// ===== Dashboard Redesign Logic =====

let dashboardRefreshTimer = null;
let lastDashboardStats = null;

function handleDashboardSearch() {
    const input = document.getElementById('dashboard-global-search');
    if (!input || !input.value.trim()) return;
    
    document.querySelector('[data-tab="tab-library"]').click();
    
    const libSearch = document.getElementById('library-search');
    if (libSearch) {
        libSearch.value = input.value;
        filterLibrary();
    }
}

async function refreshDashboardData(force = false) {
    if (!window.pywebview || !window.pywebview.api) return;
    
    // 1. Stats (Today)
    window.pywebview.api.get_stats('today').then(stats => {
        if (!stats) return;
        document.getElementById('summary-today-time').textContent = formatTimeStr(stats.total_watch_time || 0);
        document.getElementById('summary-today-eps').textContent = `${stats.unique_episodes || 0} episodes`;
    });
    
    // 2. Diagnostics (Health & Recent Activity)
    window.pywebview.api.get_diagnostics().then(diag => {
        if (!diag) return;
        
        let total = 0; let healthy = 0;
        let degraded = 0; let error = 0;
        for (const [key, comp] of Object.entries(diag.components || {})) {
            total++;
            if (comp.state === 'HEALTHY') healthy++;
            else if (comp.state === 'DEGRADED') degraded++;
            else if (comp.state === 'ERROR') error++;
        }
        
        let score = 100;
        if (total > 0) score = Math.round((healthy / total) * 100);
        
        const healthScoreEl = document.getElementById('summary-health-score');
        const healthDetailsEl = document.getElementById('summary-health-details');
        healthScoreEl.textContent = `${score}%`;
        
        if (score === 100) {
            healthScoreEl.style.color = 'var(--color-success)';
            healthDetailsEl.textContent = 'All systems online';
        } else if (error > 0) {
            healthScoreEl.style.color = '#ef4444';
            healthDetailsEl.textContent = `${error} system(s) in error`;
        } else {
            healthScoreEl.style.color = '#f59e0b';
            healthDetailsEl.textContent = `${degraded} system(s) degraded`;
        }
        
        const timelineEl = document.getElementById('dashboard-activity-list');
        if (timelineEl && diag.timeline) {
            const meaningfulTypes = ['system', 'anilist', 'library', 'metadata'];
            let meaningful = diag.timeline.filter(e => {
                const msg = (e.message || '').toLowerCase();
                if (msg.includes('cache hit') || msg.includes('resolved') || msg.includes('deduplicated') || msg.includes('scan completed') || msg.includes('scan error') || msg.includes('self-test') || msg.includes('background task')) return false;
                if (e.component === 'anilist' && (msg.includes('synced') || msg.includes('rewatch'))) return true;
                if (e.component === 'system' && (msg.includes('watching') || msg.includes('started') || msg.includes('changed') || msg.includes('completed'))) return true;
                if (msg.includes('error') || msg.includes('failed') || msg.includes('warning') || msg.includes('recovery')) return true;
                return false;
            }).reverse().slice(0, 10);
            
            if (meaningful.length === 0) {
                timelineEl.innerHTML = '<p class="empty-state">No recent activity.</p>';
            } else {
                timelineEl.innerHTML = meaningful.map(e => `
                    <div class="activity-item">
                        <span class="time">${new Date(e.timestamp * 1000).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}</span>
                        <span class="msg">${e.message}</span>
                    </div>
                `).join('');
            }
        }
    });

    // 3. AniList Sync Status
    window.pywebview.api.get_anilist_sync_status().then(sync => {
        if (!sync) return;
        const stateEl = document.getElementById('summary-sync-state');
        if(stateEl) {
            stateEl.textContent = sync.state;
            stateEl.style.color = sync.state === 'HEALTHY' ? 'var(--color-success)' : '#ef4444';
        }
        
        let pendingText = sync.queue_size === 0 ? 'All synced' : `${sync.queue_size} pending`;
        const detailsEl = document.getElementById('summary-sync-details');
        if(detailsEl) detailsEl.textContent = pendingText;
        
        const actionBanner = document.getElementById('dashboard-action-required');
        const actionMsg = document.getElementById('dashboard-action-msg');
        if (sync.state === 'ERROR' && actionBanner && actionMsg) {
            actionBanner.style.display = 'flex';
            let errMsg = sync.last_logs[sync.last_logs.length-1] || 'Unknown error';
            errMsg = errMsg.replace(/\\[AniList\\]/g, '').replace(/\\[Error\\]/g, '').trim();
            actionMsg.textContent = 'AniList Sync Error: ' + errMsg;
        } else if (actionBanner) {
            actionBanner.style.display = 'none';
        }
    });

    // 4. Continue Watching
    window.pywebview.api.get_history().then(res => {
        const rail = document.getElementById('dashboard-continue-rail');
        if (!rail) return;
        if (!res || !res.history || res.history.length === 0) {
            rail.innerHTML = '<p class="empty-state">No recent activity.</p>';
            return;
        }
        
        const seen = new Set();
        const unique = [];
        for (let item of res.history) {
            let title = item.cleaned_title || item.title;
            if (!seen.has(title)) {
                seen.add(title);
                unique.push(item);
            }
            if (unique.length >= 10) break;
        }
        
        rail.innerHTML = unique.map(item => `
            <div class="history-card" onclick="document.querySelector('[data-tab=\\'tab-library\\']').click()">
                <div class="history-cover">
                    <img src="${item.cover_url || COVER_PLACEHOLDER}" onerror="this.src='${COVER_PLACEHOLDER}'">
                </div>
                <div class="history-info">
                    <div class="history-title" title="${item.title}">${item.cleaned_title || item.title}</div>
                    <div class="history-meta">${item.episode_str || 'Movie'}</div>
                </div>
            </div>
        `).join('');
    });
    
    // 5. Airing Soon
    window.pywebview.api.get_airing_schedule().then(res => {
        const rail = document.getElementById('dashboard-airing-rail');
        const offlineBadge = document.getElementById('airing-offline-badge');
        if (!rail) return;
        
        if (!res || res.error) {
            rail.innerHTML = `<p class="empty-state">Failed to load schedule.</p>`;
            if (offlineBadge) offlineBadge.style.display = 'none';
            return;
        }
        
        if (res.status === 'offline' && offlineBadge) offlineBadge.style.display = 'inline';
        else if (offlineBadge) offlineBadge.style.display = 'none';
        
        if (!res.items || res.items.length === 0) {
            rail.innerHTML = '<p class="empty-state">No upcoming episodes for current shows.</p>';
            return;
        }
        
        rail.innerHTML = res.items.map(item => {
            const timeUntil = item.nextAiringEpisode.timeUntilAiring;
            let timeStr = "";
            if (timeUntil < 86400) {
                const hrs = Math.floor(timeUntil / 3600);
                timeStr = hrs > 0 ? `In ${hrs}h` : 'Soon';
            } else {
                const days = Math.floor(timeUntil / 86400);
                timeStr = `In ${days}d`;
            }
            
            return `
            <div class="history-card">
                <div class="history-cover">
                    <img src="${item.coverImage.medium || COVER_PLACEHOLDER}" onerror="this.src='${COVER_PLACEHOLDER}'">
                    <div class="history-progress">
                        <div class="progress-fill" style="width: 100%; background: var(--accent-blurple)"></div>
                    </div>
                </div>
                <div class="history-info">
                    <div class="history-title" title="${item.title.romaji}">${item.title.romaji}</div>
                    <div class="history-meta" style="color:var(--accent-blurple);">Ep ${item.nextAiringEpisode.episode} • ${timeStr}</div>
                </div>
            </div>
            `;
        }).join('');
    });
}

function formatTimeStr(seconds) {
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    let hrs = Math.floor(seconds / 3600);
    let mins = Math.floor((seconds % 3600) / 60);
    if (hrs > 0) return `${hrs}h ${mins}m`;
    return `${mins}m`;
}

setInterval(() => {
    const tab = document.getElementById('tab-dashboard');
    if (tab && tab.classList.contains('active')) {
        refreshDashboardData(false);
    }
}, 30000);

document.addEventListener('pywebviewready', () => {
    setTimeout(() => refreshDashboardData(true), 1500);
});
"""

with open("web/script.js", "a", encoding="utf-8") as f:
    f.write(js_code)
