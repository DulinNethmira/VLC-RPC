// ===== Format Time =====
function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "0:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

// ===== State Update from Backend =====
window.updateState = function(state) {
    // Hide loader on first update
    const loader = document.getElementById('loader');
    const app = document.getElementById('app');
    if (loader.style.display !== 'none') {
        loader.style.display = 'none';
        app.style.display = 'flex';
    }

    // Connection dots
    const vlcDot = document.getElementById('vlc-dot');
    const discordDot = document.getElementById('discord-dot');
    vlcDot.classList.toggle('online', state.vlc_connected);
    discordDot.classList.toggle('online', state.rpc_connected);

    // Now Playing logic
    const idleState = document.getElementById('idle-state');
    const activeState = document.getElementById('active-state');
    const heroBgBlur = document.getElementById('hero-bg-blur');

    const isPlaying = state.vlc_connected && state.title && (state.playback_state === 'playing' || state.playback_state === 'paused');

    if (isPlaying) {
        idleState.style.display = 'none';
        activeState.style.display = 'flex';

        // Cover image
        const coverEl = document.getElementById('hero-cover');
        const imgUrl = (state.metadata && state.metadata.image_url) ? state.metadata.image_url : (state.local_arturl ? state.local_arturl : '');
        
        if (!imgUrl) {
            coverEl.style.opacity = '0.3';
        } else {
            coverEl.style.opacity = '1';
        }
        
        if (state.metadata && state.metadata.dominant_color) {
            document.documentElement.style.setProperty('--glow-color', state.metadata.dominant_color);
        } else {
            document.documentElement.style.setProperty('--glow-color', 'rgba(67, 56, 202, 0.4)');
        }

        if (imgUrl && coverEl.src !== imgUrl) {
            coverEl.src = imgUrl;
            heroBgBlur.style.backgroundImage = `url(${imgUrl})`;
            heroBgBlur.style.opacity = '1';
        } else if (!imgUrl) {
            coverEl.src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180"><rect fill="%23222" width="180" height="180"/><text x="90" y="95" text-anchor="middle" fill="%23555" font-size="48">🎬</text></svg>';
            heroBgBlur.style.opacity = '0';
        }

        // Badge
        const badge = document.getElementById('hero-badge');
        const isMusic = state.artist && state.artist !== '' && state.artist !== 'Unknown Artist';
        if (state.playback_state === 'paused') {
            badge.textContent = 'Paused';
            badge.className = 'hero-badge paused';
        } else if (isMusic) {
            badge.textContent = 'Listening';
            badge.className = 'hero-badge listening';
        } else {
            badge.textContent = 'Watching';
            badge.className = 'hero-badge';
        }
        
        // Quality & Audio badges
        const qualityBadge = document.getElementById('quality-badge');
        if (state.quality) {
            qualityBadge.textContent = state.quality;
            qualityBadge.style.display = 'inline-block';
        } else {
            qualityBadge.style.display = 'none';
        }
        
        const audioBadge = document.getElementById('audio-badge');
        if (state.audio_tracks > 1) {
            audioBadge.textContent = state.audio_tracks + ' Audios';
            audioBadge.style.display = 'inline-block';
        } else {
            audioBadge.style.display = 'none';
        }

        // Title & Subtitle — prefer cleaned_title ("One Piece") over raw title ("One Piece 1168.mp4")
        const displayTitle = state.cleaned_title || state.title || 'Unknown';
        document.getElementById('hero-title').textContent = displayTitle;
        document.getElementById('hero-subtitle').textContent = state.episode_str || (isMusic ? state.artist : '');

        // Progress
        const currentSecs = state.time || 0;
        const totalSecs = state.length || 0;
        document.getElementById('time-current').textContent = formatTime(currentSecs);
        document.getElementById('time-total').textContent = totalSecs > 0 ? formatTime(totalSecs) : '--:--';

        const pct = totalSecs > 0 ? (currentSecs / totalSecs) * 100 : 0;
        document.getElementById('progress-fill').style.width = pct + '%';

        // Update Discord Preview
        document.getElementById('dc-large-img').src = imgUrl || 'icon.png';
        if (imgUrl) {
            document.getElementById('dc-small-img-container').style.display = 'flex';
            document.getElementById('dc-small-img').src = 'icon.png';
        } else {
            document.getElementById('dc-small-img-container').style.display = 'none';
        }
        
        document.getElementById('dc-activity-type').textContent = isMusic ? 'Listening to' : 'Watching';
        document.getElementById('dc-details').textContent = displayTitle;
        document.getElementById('dc-state').textContent = state.episode_str || (isMusic ? 'by ' + state.artist : '');
        
        if (state.playback_state === 'playing' && totalSecs > 0) {
            const remaining = totalSecs - currentSecs;
            document.getElementById('dc-time').textContent = formatTime(remaining) + ' left';
        } else if (state.playback_state === 'paused') {
            document.getElementById('dc-time').textContent = 'Paused';
        } else {
            document.getElementById('dc-time').textContent = formatTime(currentSecs) + ' elapsed';
        }

    } else {
        idleState.style.display = 'flex';
        activeState.style.display = 'none';
        heroBgBlur.style.opacity = '0';
        
        // Reset Discord Preview
        document.getElementById('dc-large-img').src = 'icon.png';
        document.getElementById('dc-small-img-container').style.display = 'none';
        document.getElementById('dc-details').textContent = 'Waiting for media...';
        document.getElementById('dc-state').textContent = '';
        document.getElementById('dc-time').textContent = '';
    }
}

// ===== Force Sync =====
function refreshStatus() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.force_update();
    }
}

// ===== Save Config =====
function saveConfig() {
    const config = {
        client_id: document.getElementById('client_id').value,
        vlc_host: document.getElementById('vlc_host').value,
        vlc_port: parseInt(document.getElementById('vlc_port').value) || 8080,
        vlc_password: document.getElementById('vlc_password').value,
        anilist_client_id: document.getElementById('anilist_client_id').value,
        anilist_client_secret: document.getElementById('anilist_client_secret').value,
        discord_app_secret: document.getElementById('discord_app_secret').value,
        discord_app_id: document.getElementById('discord_app_id').value,
        auto_sync_threshold: parseInt(document.getElementById('auto_sync_threshold').value) || 90,
        gemini_api_key: document.getElementById('gemini_api_key').value
    };
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.save_config(config).then(function(response) {
            if (response.success) {
                alert('Settings saved!');
            } else {
                alert('Error: ' + response.error);
            }
        }).catch(err => {
            console.error("Failed to load config", err);
        });
    }
}

function switchTab(tabId) {
    document.querySelectorAll('.tab-content').forEach(t => {
        t.style.display = 'none';
        t.classList.remove('active');
    });
    
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    
    let target = document.getElementById(tabId) || document.getElementById('tab-' + tabId.replace('tab-', ''));
    if(target) {
        target.style.display = 'block';
        target.classList.add('active');
    }
    
    let btn = document.querySelector('[data-tab="' + tabId + '"]') || document.querySelector('[data-tab="tab-' + tabId + '"]');
    if(btn) btn.classList.add('active');
    
    if (tabId.includes('history')) {
        startHistoryRefresh();
    } else {
        stopHistoryRefresh();
    }
    if (tabId.includes('anilogs')) {
        startAniLogRefresh();
    } else {
        stopAniLogRefresh();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            let tab = item.getAttribute('data-tab');
            if(tab) switchTab(tab);
        });
    });
    
    // Existing tabs might use old onclick
    let oldBtnHome = document.getElementById('btn-home');
    if (oldBtnHome) oldBtnHome.onclick = (e) => { e.preventDefault(); switchTab('tab-dashboard'); };
    
    let oldBtnSettings = document.getElementById('btn-settings');
    if (oldBtnSettings) oldBtnSettings.onclick = (e) => { e.preventDefault(); switchTab('tab-preferences'); };
});

let historyInterval = null;

function loadHistory() {
    if (!window.pywebview || !window.pywebview.api) return;
    window.pywebview.api.get_history().then(res => {
        if(res && res.success) {
            let total = res.total_time;
            let hrs = Math.floor(total / 3600);
            let mins = Math.floor((total % 3600) / 60);
            document.getElementById('total-time').innerText = `${hrs}h ${mins}m`;
            
            let list = document.getElementById('history-list');
            list.innerHTML = '';
            res.history.forEach(item => {
                let durMins = Math.ceil(item.duration / 60);
                let div = document.createElement('div');
                div.className = 'history-item' + (item.live ? ' history-live' : '');
                let timeLabel = item.live 
                    ? `<span class="live-badge"><span class="live-dot"></span> LIVE</span>` 
                    : item.timestamp;
                div.innerHTML = `
                    <div class="h-icon"><i class="${item.is_music ? 'fas fa-music' : 'fas fa-film'}"></i></div>
                    <div class="h-details">
                        <h4>${item.title}</h4>
                        <p>${item.episode_str || (item.is_music ? 'Song' : 'Video')} • ${durMins} min${durMins !== 1 ? 's' : ''}</p>
                    </div>
                    <div class="h-time">${timeLabel}</div>
                `;
                list.appendChild(div);
            });
        }
    });
}

function startHistoryRefresh() {
    loadHistory();
    if (historyInterval) clearInterval(historyInterval);
    historyInterval = setInterval(loadHistory, 5000);
}

function stopHistoryRefresh() {
    if (historyInterval) { clearInterval(historyInterval); historyInterval = null; }
}

// ===== Load Config on Start =====
window.addEventListener('pywebviewready', function() {
    window.pywebview.api.get_config().then(function(config) {
        document.getElementById('client_id').value = config.client_id || '';
        document.getElementById('vlc_host').value = config.vlc_host || 'localhost';
        document.getElementById('vlc_port').value = config.vlc_port || 8080;
        document.getElementById('vlc_password').value = config.vlc_password || '';
        document.getElementById('anilist_client_id').value = config.anilist_client_id || '';
        document.getElementById('anilist_client_secret').value = config.anilist_client_secret || '';
        document.getElementById('discord_app_secret').value = config.discord_client_secret || config.discord_app_secret || '';
        document.getElementById('discord_app_id').value = config.discord_app_id || config.discord_client_id || '';
        document.getElementById('auto_sync_threshold').value = config.auto_sync_threshold || 90;
        document.getElementById('gemini_api_key').value = config.gemini_api_key || '';
    });
    
    document.getElementById('btn-anilist-login').addEventListener('click', (e) => {
        e.preventDefault();
        window.pywebview.api.auth_anilist();
    });

    // Start polling state from backend safely
    setInterval(() => {
        window.pywebview.api.get_state().then(state => {
            if (state) window.updateState(state);

            // ── Update checker ──────────────────────────────────────────────
            if (state && state.update_available && !window.updatePromptShown) {
                window.updatePromptShown = true;
                const modal = document.getElementById('update-modal');
                const verLabel = document.getElementById('update-version-label');
                const changelogBox = document.getElementById('update-changelog-box');
                const dlBtn = document.getElementById('update-download-btn');
                const btnVer = document.getElementById('update-btn-ver');

                if (verLabel) verLabel.textContent = `v${state.update_version} is available — you have v${state.current_version || '?'}`;
                if (changelogBox) changelogBox.textContent = state.update_changelog || 'See GitHub for details.';
                if (btnVer) btnVer.textContent = state.update_version;
                if (dlBtn) {
                    dlBtn.onclick = () => {
                        dlBtn.disabled = true;
                        dlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Downloading...';
                        window.pywebview.api.trigger_download_update();
                    };
                }
                if (modal) modal.style.display = 'flex';
            }

            if (state && state.update_status === "downloading") {
                const dlBtn = document.getElementById('update-download-btn');
                if (dlBtn) {
                    dlBtn.disabled = true;
                    dlBtn.innerHTML = `<i class="fas fa-spinner fa-spin"></i> Downloading... ${state.update_progress || 0}%`;
                }
            } else if (state && state.update_status === "ready") {
                const dlBtn = document.getElementById('update-download-btn');
                if (dlBtn && dlBtn.dataset.ready !== "true") {
                    dlBtn.dataset.ready = "true";
                    dlBtn.disabled = false;
                    dlBtn.style.background = "#22c55e";
                    dlBtn.style.borderColor = "#16a34a";
                    dlBtn.style.color = "#fff";
                    dlBtn.innerHTML = '<i class="fas fa-box-open"></i> Install & Restart';
                    dlBtn.onclick = () => {
                        dlBtn.disabled = true;
                        dlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Installing...';
                        window.pywebview.api.install_update();
                    };
                }
            } else if (state && state.update_status === "error") {
                const dlBtn = document.getElementById('update-download-btn');
                if (dlBtn && dlBtn.dataset.error !== "true") {
                    dlBtn.dataset.error = "true";
                    dlBtn.disabled = false;
                    dlBtn.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Download Failed (Try Browser)';
                    dlBtn.onclick = () => window.open(state.update_download_url, '_blank');
                }
            }
        }).catch(err => console.error("Error fetching state:", err));
        
        // Also poll config to update AniList connect button
        window.pywebview.api.get_config().then(config => {
            const btn = document.getElementById('btn-anilist-login');
            if (config && config.anilist_token) {
                btn.style.background = 'rgba(34, 197, 94, 0.2)';
                btn.style.borderColor = '#22c55e';
                btn.innerHTML = '<i class="fas fa-check-circle" style="color: #22c55e;"></i> <span style="color: #22c55e;">AniList Connected</span>';
            } else {
                btn.style.background = '#2b2d42';
                btn.style.borderColor = '#3b82f6';
                btn.innerHTML = '<i class="fas fa-link"></i> <span>Connect AniList Account</span>';
            }
        }).catch(err => {});
    }, 1500);

    // Backend state now handles version.
});
// ===== AniList Logs =====
let aniLogInterval = null;
let _lastAniLogCount = 0;

function renderAniLogs(logs) {
    const el = document.getElementById('anilog-list');
    if (!el) return;
    if (logs.length === 0) {
        el.innerHTML = '<p style="color: #555; text-align: center; margin: 40px 0;">No AniList activity yet. Start playing an anime episode to see logs here.</p>';
        return;
    }
    if (logs.length === _lastAniLogCount) return; // no change
    _lastAniLogCount = logs.length;
    el.innerHTML = [...logs].reverse().map(line => {
        let color = '#c8d3f0';
        if (line.includes('[Error]') || line.includes('[Crash]')) color = '#f87171';
        else if (line.includes('[Trigger]') || line.includes('Updated!')) color = '#4ade80';
        else if (line.includes('[Found]') || line.includes('[Global]')) color = '#60a5fa';
        else if (line.includes('[Check]')) color = '#a78bfa';
        else if (line.includes('[Skip]')) color = '#94a3b8';
        return `<div style="color:${color}; padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.04);">${line}</div>`;
    }).join('');
}

function loadAniLogs() {
    if (!window.pywebview || !window.pywebview.api) return;
    window.pywebview.api.get_anilist_logs().then(res => {
        if (res && res.success) renderAniLogs(res.logs);
    }).catch(() => {});
}

function startAniLogRefresh() {
    loadAniLogs();
    if (aniLogInterval) clearInterval(aniLogInterval);
    aniLogInterval = setInterval(loadAniLogs, 2000);
}

function stopAniLogRefresh() {
    if (aniLogInterval) { clearInterval(aniLogInterval); aniLogInterval = null; }
}

function clearAniLogs() {
    _lastAniLogCount = 0;
    if (window.pywebview && window.pywebview.api) {
        // Also clear on backend by calling a no-op; we just reset frontend
        window.pywebview.api.get_anilist_logs().then(() => {});
    }
    const el = document.getElementById('anilog-list');
    if (el) el.innerHTML = '<p style="color:#555; text-align:center; margin:40px 0;">Logs cleared.</p>';
}

// ===== Interactive Developer Console =====
window.addLog = function(msg) {
    const body = document.getElementById('console-body');
    const line = document.createElement('div');
    line.className = 'log-line';
    line.textContent = msg;
    body.appendChild(line);
    body.scrollTop = body.scrollHeight;
};

window.toggleConsole = function() {
    const consoleEl = document.getElementById('dev-console');
    const icon = document.getElementById('console-toggle-icon');
    if (consoleEl.classList.contains('collapsed')) {
        consoleEl.classList.remove('collapsed');
        icon.className = 'fas fa-chevron-down';
    } else {
        consoleEl.classList.add('collapsed');
        icon.className = 'fas fa-chevron-up';
    }
};

// ===== Advanced Stats & Graphs =====
let mediaPieChart = null;
let weeklyBarChart = null;

window.fetchStats = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_stats().then(stats => {
            document.getElementById('total-time-large').textContent = formatTime(stats.total_watch_time);
            
            // Render Pie Chart
            const pieCtx = document.getElementById('mediaPieChart').getContext('2d');
            if (mediaPieChart) mediaPieChart.destroy();
            mediaPieChart = new Chart(pieCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Anime', 'Movies', 'TV Shows', 'Music'],
                    datasets: [{
                        data: [
                            stats.media_types.anime || 0,
                            stats.media_types.movie || 0,
                            stats.media_types.tv_show || 0,
                            stats.media_types.music || 0
                        ],
                        backgroundColor: ['#5865F2', '#e8772e', '#43b581', '#f04747'],
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#eaeaf0' } }
                    }
                }
            });

            // Render Bar Chart
            const barCtx = document.getElementById('weeklyBarChart').getContext('2d');
            if (weeklyBarChart) weeklyBarChart.destroy();
            const days = ['6 Days Ago', '5 Days Ago', '4 Days Ago', '3 Days Ago', '2 Days Ago', 'Yesterday', 'Today'];
            weeklyBarChart = new Chart(barCtx, {
                type: 'bar',
                data: {
                    labels: days,
                    datasets: [{
                        label: 'Watch Time (Minutes)',
                        data: stats.recent_activity.map(s => Math.round(s / 60)),
                        backgroundColor: '#5865F2',
                        borderRadius: 4
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { ticks: { color: '#6e6e82' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                        x: { ticks: { color: '#6e6e82' }, grid: { display: false } }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        });
    }
};

// Hook tab switching to fetch stats
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        if (item.dataset.tab === 'tab-history') {
            fetchStats();
        }
    });
});

