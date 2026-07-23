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

    } else {
        idleState.style.display = 'flex';
        activeState.style.display = 'none';
        heroBgBlur.style.opacity = '0';
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
