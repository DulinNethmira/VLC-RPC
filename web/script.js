// ===== Format Time =====
function formatTotalHours(seconds) {
    if (isNaN(seconds) || seconds <= 0) return "0h 0m";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (h > 0) return h + "h " + m + "m";
    return m + "m";
}
function formatTime(seconds) {
    if (isNaN(seconds) || seconds < 0) return "0:00";
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    return `${m}:${s.toString().padStart(2, '0')}`;
}

const COVER_PLACEHOLDER = 'data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="180" height="180" viewBox="0 0 180 180"%3E%3Crect fill="%2322222a" width="180" height="180"/%3E%3Cpath d="M50 56h80v68H50z" fill="%2330303a"/%3E%3Cpath d="M58 70h64M58 86h64M58 102h42" stroke="%235b6070" stroke-width="8" stroke-linecap="round"/%3E%3C/svg%3E';

function parseMarkdown(text) {
    if (!text) return '';
    let html = text
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;') // escape html
        .replace(/### (.*?)\n/g, '<h3 style="color:var(--text-primary); margin:8px 0 4px;">$1</h3>\n')
        .replace(/#### (.*?)\n/g, '<h4 style="color:var(--text-primary); margin:6px 0 2px;">$1</h4>\n')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/`(.*?)`/g, '<code style="background:rgba(255,255,255,0.1); padding:2px 4px; border-radius:3px; font-family:monospace;">$1</code>')
        .replace(/^- (.*)/gm, '<li style="margin-left:16px;">$1</li>');
        
    html = html.replace(/(<li.*?>.*?<\/li>\n?)+/g, '<ul style="margin:4px 0; padding:0;">$&</ul>');
    html = html.replace(/\n/g, '<br>');
    return html;
}

function getRatingText(metadata) {
    if (!metadata) return '';
    const rating = metadata.episode_rating || metadata.rating || metadata.imdb_rating || '';
    if (rating === null || rating === undefined || rating === '') return '';
    const numeric = Number(rating);
    const cleanRating = Number.isFinite(numeric) ? numeric.toFixed(1).replace(/\.0$/, '') : String(rating);
    return `★ ${cleanRating}`;
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
        // Cover image hierarchy: scene snapshot -> metadata.image_url -> metadata.image_data_uri -> VLC embedded art -> placeholder
        const coverEl = document.getElementById('hero-cover');
        const snapshotUrl = state.scene_snapshot_data_uri || state.scene_snapshot_url || '';
        const onlineImgUrl = (state.metadata && (state.metadata.image_url || state.metadata.image_data_uri)) || '';
        const localImgUrl = state.local_arturl || '';
        const imgUrl = snapshotUrl || onlineImgUrl || localImgUrl || '';

        coverEl.onerror = () => {
            console.warn('[Frontend Cover Error] Failed to load:', coverEl.src);
            if (localImgUrl && coverEl.dataset.fallbackTried !== 'local' && coverEl.src !== localImgUrl) {
                coverEl.dataset.fallbackTried = 'local';
                coverEl.src = localImgUrl;
                heroBgBlur.style.backgroundImage = `url(${localImgUrl})`;
                heroBgBlur.style.opacity = '1';
                coverEl.style.opacity = '1';
                return;
            }
            coverEl.dataset.fallbackTried = 'placeholder';
            coverEl.src = COVER_PLACEHOLDER;
            coverEl.style.opacity = '0.3';
            heroBgBlur.style.opacity = '0';
        };

        if (state.metadata && state.metadata.dominant_color) {
            document.documentElement.style.setProperty('--glow-color', state.metadata.dominant_color);
        } else {
            document.documentElement.style.setProperty('--glow-color', 'rgba(67, 56, 202, 0.4)');
        }

        if (imgUrl && coverEl.dataset.requestedSrc !== imgUrl) {
            coverEl.dataset.requestedSrc = imgUrl;
            coverEl.dataset.fallbackTried = '';
            coverEl.src = imgUrl;
            heroBgBlur.style.backgroundImage = `url(${imgUrl})`;
            heroBgBlur.style.opacity = '1';
            coverEl.style.opacity = '1';
        } else if (!imgUrl && coverEl.dataset.fallbackTried !== 'placeholder') {
            coverEl.dataset.requestedSrc = '';
            coverEl.dataset.fallbackTried = 'placeholder';
            coverEl.src = COVER_PLACEHOLDER;
            coverEl.style.opacity = '0.3';
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
        } else if (state.watch_mode === 'REWATCH') {
            badge.textContent = `↻ Rewatching #${state.rewatch_number || 1}`;
            badge.className = 'hero-badge rewatching';
        } else {
            badge.textContent = 'Watching';
            badge.className = 'hero-badge';
        }
        
        const btnRewatch = document.getElementById('btn-start-rewatch');
        if (btnRewatch) {
            const isCompleted = state.anilist_identity && state.anilist_identity.media_list && state.anilist_identity.media_list.status === 'COMPLETED';
            if (state.watch_mode !== 'REWATCH' && isCompleted && !isMusic && state.anilist_identity.validated) {
                btnRewatch.style.display = 'inline-block';
                btnRewatch.disabled = Boolean(state.rewatch_starting);
                btnRewatch.textContent = state.rewatch_starting ? 'Starting Rewatch...' : '↻ Start Rewatch';
            } else {
                btnRewatch.style.display = 'none';
            }
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
        const ratingText = getRatingText(state.metadata);
        const subtitleParts = [];
        if (state.episode_str) subtitleParts.push(state.episode_str);
        else if (isMusic && state.artist) subtitleParts.push(state.artist);
        if (ratingText) subtitleParts.push(ratingText);
        document.getElementById('hero-title').textContent = displayTitle;
        document.getElementById('hero-subtitle').textContent = subtitleParts.join(' • ');

        // Progress
        const currentSecs = state.time || 0;
        const totalSecs = state.length || 0;
        document.getElementById('time-current').textContent = formatTime(currentSecs);
        document.getElementById('time-total').textContent = totalSecs > 0 ? formatTime(totalSecs) : '--:--';

        const pct = totalSecs > 0 ? (currentSecs / totalSecs) * 100 : 0;
        document.getElementById('progress-fill').style.width = pct + '%';

        // Update Discord Preview
        const dcLargeImg = document.getElementById('dc-large-img');
        dcLargeImg.onerror = () => { dcLargeImg.src = 'icon.png'; };
        dcLargeImg.src = imgUrl || 'icon.png';
        if (imgUrl) {
            document.getElementById('dc-small-img-container').style.display = 'flex';
            document.getElementById('dc-small-img').src = 'icon.png';
        } else {
            document.getElementById('dc-small-img-container').style.display = 'none';
        }
        
        document.getElementById('dc-activity-type').textContent = isMusic ? 'Listening to' : 'Watching';
        document.getElementById('dc-details').textContent = displayTitle;
        const dcStateParts = [];
        if (state.episode_str) dcStateParts.push(state.episode_str);
        else if (isMusic && state.artist) dcStateParts.push('by ' + state.artist);
        if (ratingText) dcStateParts.push(ratingText);
        document.getElementById('dc-state').textContent = dcStateParts.join(' • ');
        
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

function startRewatch() {
    const button = document.getElementById('btn-start-rewatch');
    if (!button || button.disabled || !window.pywebview || !window.pywebview.api) return;
    button.disabled = true;
    button.textContent = 'Starting Rewatch...';
    window.pywebview.api.manual_start_rewatch().then(result => {
        if (!result || !result.success) {
            button.disabled = false;
            button.textContent = '↻ Start Rewatch';
        }
    }).catch(() => {
        button.disabled = false;
        button.textContent = '↻ Start Rewatch';
    });
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
        discord_widget_bot_token: document.getElementById('discord_widget_bot_token').value,
        discord_widget_app_id: document.getElementById('discord_widget_app_id').value,
        discord_widget_user_id: document.getElementById('discord_widget_user_id').value,
        auto_sync_threshold: parseInt(document.getElementById('auto_sync_threshold').value) || 90,
        gemini_api_key: document.getElementById('gemini_api_key').value,
        scene_snapshots: document.getElementById('scene_snapshots').value === 'true',
        aniskip_auto_skip: document.getElementById('aniskip_auto_skip').checked,
        auto_score_popup: document.getElementById('auto_score_popup').checked,
        telemetry_enabled: document.getElementById('telemetry_enabled').checked,
        theme_color: document.getElementById('theme_selector').value
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

window.applyTheme = function(color) {
    document.documentElement.style.setProperty('--accent-blurple', color);
    let r = parseInt(color.slice(1, 3), 16),
        g = parseInt(color.slice(3, 5), 16),
        b = parseInt(color.slice(5, 7), 16);
    document.documentElement.style.setProperty('--glow-color', `rgba(${r}, ${g}, ${b}, 0.4)`);

    if (weeklyBarChart) {
        weeklyBarChart.data.datasets[0].backgroundColor = color;
        weeklyBarChart.update();
    }
    if (window._anaWeeklyChart) {
        window._anaWeeklyChart.data.datasets[0].backgroundColor = color;
        window._anaWeeklyChart.data.datasets[0].borderColor = color;
        window._anaWeeklyChart.update();
    }
};

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
    if (tabId.includes('analytics')) {
        loadAnalytics();
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
function initPyWebview() {
    window.pywebview.api.get_config().then(function(config) {
        document.getElementById('client_id').value = config.client_id || '';
        document.getElementById('vlc_host').value = config.vlc_host || 'localhost';
        document.getElementById('vlc_port').value = config.vlc_port || 8080;
        document.getElementById('vlc_password').value = config.vlc_password || '';
        document.getElementById('anilist_client_id').value = config.anilist_client_id || '';
        document.getElementById('anilist_client_secret').value = config.anilist_client_secret || '';
        document.getElementById('discord_app_secret').value = config.discord_client_secret || config.discord_app_secret || '';
        document.getElementById('discord_app_id').value = config.discord_app_id || config.discord_client_id || '';
        document.getElementById('discord_widget_bot_token').value = config.discord_widget_bot_token || '';
        document.getElementById('discord_widget_app_id').value = config.discord_widget_app_id || '';
        document.getElementById('discord_widget_user_id').value = config.discord_widget_user_id || '';
        document.getElementById('auto_sync_threshold').value = config.auto_sync_threshold || 90;
        document.getElementById('gemini_api_key').value = config.gemini_api_key || '';
        document.getElementById('scene_snapshots').value = (config.scene_snapshots !== false) ? 'true' : 'false';
        document.getElementById('aniskip_auto_skip').checked = !!config.aniskip_auto_skip;
        document.getElementById('auto_score_popup').checked = (config.auto_score_popup !== false);
        document.getElementById('telemetry_enabled').checked = (config.telemetry_enabled !== false);
        if (config.theme_color) {
            document.getElementById('theme_selector').value = config.theme_color;
            applyTheme(config.theme_color);
        }
    });
    
    document.getElementById('btn-anilist-login').addEventListener('click', (e) => {
        e.preventDefault();
        window.pywebview.api.auth_anilist();
    });

    // Check Cloud Account Status
    window.pywebview.api.get_cloud_account().then(res => {
        if (res.logged_in) {
            document.getElementById('account-logged-out').style.display = 'none';
            document.getElementById('account-logged-in').style.display = 'block';
            document.getElementById('cloud_current_email').textContent = res.email;
            loadCloudDevices();
        }
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
                if (changelogBox) changelogBox.innerHTML = parseMarkdown(state.update_changelog || 'See GitHub for details.');
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
}

if (window.pywebview && window.pywebview.api) {
    initPyWebview();
} else {
    window.addEventListener('pywebviewready', initPyWebview);
}

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
window.toggleDiscordRPC = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.toggle_rpc().then(enabled => {
            const btn = document.getElementById('btn-toggle-rpc');
            if (enabled) {
                btn.innerHTML = '<i class="fas fa-power-off"></i> RPC Active';
                btn.style.borderColor = '#34d399';
                btn.style.color = '#34d399';
            } else {
                btn.innerHTML = '<i class="fas fa-power-off"></i> RPC Paused';
                btn.style.borderColor = '#ef4444';
                btn.style.color = '#ef4444';
            }
        });
    }
};

// ===== Advanced Stats & Graphs =====
let mediaPieChart = null;
let weeklyBarChart = null;

window.fetchStats = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_stats().then(stats => {
            document.getElementById('total-time-large').textContent = formatTotalHours(stats.total_watch_time);
            
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

            // Render Bar Chart — recent_activity is already in minutes
            const barCtx = document.getElementById('weeklyBarChart').getContext('2d');
            if (weeklyBarChart) weeklyBarChart.destroy();
            const days = ['6 Days Ago', '5 Days Ago', '4 Days Ago', '3 Days Ago', '2 Days Ago', 'Yesterday', 'Today'];
            weeklyBarChart = new Chart(barCtx, {
                type: 'bar',
                data: {
                    labels: days,
                    datasets: [{
                        label: 'Watch Time (Hours)',
                        data: stats.recent_activity,
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

            // Render recent history list
            const historyList = document.getElementById('history-list');
            if (historyList) {
                if (!stats.history || stats.history.length === 0) {
                    historyList.innerHTML = '<p class="empty-state">No history yet. Start watching something!</p>';
                } else {
                    historyList.innerHTML = stats.history.map(entry => {
                        const mins = Math.round(entry.duration / 60);
                        const label = entry.is_music ? '🎵' : '🎬';
                        return `<div class="history-entry">
                            <span class="history-icon">${label}</span>
                            <div class="history-info">
                                <span class="history-title">${entry.title}</span>
                                <span class="history-meta">${entry.episode || ''} &bull; ${mins} min &bull; ${entry.timestamp}</span>
                            </div>
                        </div>`;
                    }).join('');
                }
            }
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

// === Manual Check for Updates ===
function checkUpdates() {
    const btn = document.querySelector('button[onclick="checkUpdates()"]');
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Checking...';
    }

    window.pywebview.api.manual_check_for_updates().then(result => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-arrow-up"></i> Check for Updates';
        }

        if (result && result.update_available) {
            // Populate and show the existing update modal
            window.updatePromptShown = true;
            const modal = document.getElementById('update-modal');
            const verLabel = document.getElementById('update-version-label');
            const changelogBox = document.getElementById('update-changelog-box');
            const dlBtn = document.getElementById('update-download-btn');
            const btnVer = document.getElementById('update-btn-ver');

            if (verLabel) verLabel.textContent = `v${result.update_version} is available — you have v${result.current_version || '?'}`;
            if (changelogBox) changelogBox.innerHTML = parseMarkdown(result.update_changelog || 'See GitHub for details.');
            if (btnVer) btnVer.textContent = result.update_version;
            if (dlBtn) {
                dlBtn.dataset.ready = "";
                dlBtn.dataset.error = "";
                dlBtn.disabled = false;
                dlBtn.style.background = "";
                dlBtn.style.borderColor = "";
                dlBtn.style.color = "";
                dlBtn.innerHTML = '<i class="fas fa-download"></i> Download Update';
                dlBtn.onclick = () => {
                    dlBtn.disabled = true;
                    dlBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Downloading...';
                    window.pywebview.api.trigger_download_update();
                };
            }
            if (modal) modal.style.display = 'flex';
        } else {
            // Show a "you're up to date" toast
            const toast = document.createElement('div');
            toast.style.cssText = `
                position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
                background: #1e1e2e; border: 1px solid #43b581; color: #43b581;
                padding: 12px 24px; border-radius: 12px; font-size: 0.9rem;
                font-weight: 600; z-index: 9999; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
                display: flex; align-items: center; gap: 10px; animation: fadeIn 0.3s ease;
            `;
            toast.innerHTML = '<i class="fas fa-check-circle"></i> You\'re up to date! (v' + (result.current_version || '?') + ')';
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3500);
        }
    }).catch(() => {
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<i class="fas fa-arrow-up"></i> Check for Updates';
        }
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%);
            background: #1e1e2e; border: 1px solid #ed4245; color: #ed4245;
            padding: 12px 24px; border-radius: 12px; font-size: 0.9rem;
            font-weight: 600; z-index: 9999; box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            display: flex; align-items: center; gap: 10px;
        `;
        toast.innerHTML = '<i class="fas fa-exclamation-triangle"></i> Could not reach GitHub. Check your connection.';
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3500);
    });
}

let _anaWeeklyChart = null;

function loadAnalytics() {
    if (!window.pywebview || !window.pywebview.api) return;
    const timeRange = document.getElementById('time-range-select') ? document.getElementById('time-range-select').value : 'all';
    
    window.pywebview.api.get_stats(timeRange).then(stats => {
        if (!stats) return;

        // ── Summary Cards ──────────────────────────────────────────────
        const totalSec = stats.total_watch_time || 0;
        const totalHoursEl = document.getElementById('ana-total-hours');
        if (totalHoursEl) totalHoursEl.textContent = (totalSec / 3600).toFixed(1);

        const totalAnimeEl = document.getElementById('ana-total-anime');
        if (totalAnimeEl) totalAnimeEl.textContent = stats.total_anime || 0;

        const uniqueEpsEl = document.getElementById('ana-unique-episodes');
        if (uniqueEpsEl) uniqueEpsEl.textContent = stats.unique_episodes || 0;
        
        const compEpsEl = document.getElementById('ana-completed-episodes');
        if (compEpsEl) compEpsEl.textContent = stats.completed_episodes || 0;
        
        const bingeDayEl = document.getElementById('ana-binge-day');
        if (bingeDayEl) bingeDayEl.textContent = stats.binge_day || "--";

        // ── 7-Day Chart ──────────────────────────────────────────────────
        const labels = [];
        const dayNames = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
        for (let i = 6; i >= 0; i--) {
            const d = new Date();
            d.setDate(d.getDate() - i);
            labels.push(dayNames[d.getDay()]);
        }
        const weekData = (stats.recent_activity || Array(7).fill(0)).slice(-7);

        const ctx = document.getElementById('ana-weekly-chart').getContext('2d');
        if (_anaWeeklyChart) _anaWeeklyChart.destroy();
        _anaWeeklyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Hours',
                    data: weekData,
                    backgroundColor: 'rgba(167, 139, 250, 0.7)',
                    borderColor: '#a78bfa',
                    borderWidth: 2,
                    borderRadius: 6,
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' } },
                    y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(255,255,255,0.05)' }, beginAtZero: true }
                },
                animation: { duration: 600, easing: 'easeOutQuart' }
            }
        });

        // ── Top Titles ──────────────────────────────────────────────────
        const topMap = {};
        (stats.history || []).forEach(h => {
            if (!h.title) return;
            topMap[h.title] = (topMap[h.title] || 0) + (h.duration || 0);
        });
        const topList = Object.entries(topMap).sort((a, b) => b[1] - a[1]).slice(0, 7);
        const maxDur = topList.length ? topList[0][1] : 1;
        const listEl = document.getElementById('ana-top-list');
        listEl.innerHTML = '';
        if (topList.length === 0) {
            listEl.innerHTML = '<p style="color:#555;font-size:12px;text-align:center;margin-top:20px;">No data yet. Start watching!</p>';
            return;
        }
        const colors = ['#a78bfa','#38bdf8','#34d399','#f97316','#fbbf24','#f472b6','#60a5fa'];
        topList.forEach(([title, dur], i) => {
            const hrs = (dur / 3600).toFixed(1);
            const pct = Math.round((dur / maxDur) * 100);
            const color = colors[i % colors.length];
            const row = document.createElement('div');
            row.style.cssText = 'display:flex;flex-direction:column;gap:3px;';
            row.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;">
                    <span style="font-size:12px;color:#e2e8f0;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:180px;" title="${title}">${title}</span>
                    <span style="font-size:11px;color:#94a3b8;flex-shrink:0;margin-left:8px;">${hrs}h</span>
                </div>
                <div style="background:rgba(255,255,255,0.07);border-radius:4px;height:5px;">
                    <div style="background:${color};width:${pct}%;height:5px;border-radius:4px;transition:width 0.5s ease;"></div>
                </div>`;
            listEl.appendChild(row);
        });
    }).catch(err => console.error('Analytics error:', err));
}


window.shareAnimeWrap = function() {
    const wrapArea = document.getElementById('tab-analytics');
    if (typeof html2canvas === 'undefined') {
        alert("Screenshot engine is loading... please try again in a few seconds.");
        return;
    }
    const oldBg = wrapArea.style.background;
    wrapArea.style.background = '#08080c';
    wrapArea.style.padding = '20px';
    wrapArea.style.borderRadius = '16px';
    
    html2canvas(wrapArea, {
        backgroundColor: '#08080c',
        scale: 2
    }).then(canvas => {
        wrapArea.style.background = oldBg;
        wrapArea.style.padding = '';
        wrapArea.style.borderRadius = '';
        const link = document.createElement('a');
        link.download = 'Anime-Wrap-' + new Date().toISOString().slice(0, 10) + '.png';
        link.href = canvas.toDataURL('image/png');
        link.click();
    });
};

function cloudLogin() {
    const email = document.getElementById('cloud_email').value;
    const password = document.getElementById('cloud_password').value;
    if (!email || !password) return alert("Please enter email and password");
    
    window.pywebview.api.auth_cloud_login(email, password).then(res => {
        if (res.success) {
            document.getElementById('account-logged-out').style.display = 'none';
            document.getElementById('account-logged-in').style.display = 'block';
            document.getElementById('cloud_current_email').textContent = res.email;
            loadCloudDevices();
        } else {
            alert("Login Failed: " + res.error);
        }
    });
}

function cloudRegister() {
    const email = document.getElementById('cloud_email').value;
    const password = document.getElementById('cloud_password').value;
    if (!email || !password) return alert("Please enter email and password");
    
    window.pywebview.api.auth_cloud_register(email, password).then(res => {
        if (res.success) {
            alert("Registration successful! You can now log in.");
        } else {
            alert("Registration Failed: " + res.error);
        }
    });
}

function cloudLogout() {
    window.pywebview.api.auth_cloud_logout().then(() => {
        document.getElementById('account-logged-out').style.display = 'block';
        document.getElementById('account-logged-in').style.display = 'none';
        document.getElementById('cloud_email').value = "";
        document.getElementById('cloud_password').value = "";
    });
}

function loadCloudDevices() {
    window.pywebview.api.get_cloud_devices().then(res => {
        const list = document.getElementById('cloud_devices_list');
        list.innerHTML = "";
        
        if (res.success && res.devices) {
            if (res.devices.length === 0) {
                list.innerHTML = `<div style="padding: 10px; color: var(--text-secondary); text-align: center;">No devices connected.</div>`;
                return;
            }
            res.devices.forEach(dev => {
                const devCard = document.createElement('div');
                devCard.style = "display: flex; justify-content: space-between; align-items: center; padding: 10px; background: rgba(255,255,255,0.05); border-radius: 6px;";
                devCard.innerHTML = `
                    <div>
                        <div style="font-weight: bold;">${dev.platform || 'Unknown'} (v${dev.app_version || '?'})</div>
                        <div style="font-size: 0.8em; color: var(--text-secondary);">Last seen: ${new Date(dev.last_seen).toLocaleString()}</div>
                        <div style="font-size: 0.7em; color: var(--text-secondary); opacity: 0.7;">ID: ${dev.id}</div>
                    </div>
                    <button class="action-btn" style="padding: 6px 12px; background: rgba(239, 68, 68, 0.2); color: #ef4444; border: none;" onclick="revokeCloudDevice('${dev.id}')">
                        Revoke
                    </button>
                `;
                list.appendChild(devCard);
            });
        } else {
            list.innerHTML = `<div style="padding: 10px; color: #ef4444; text-align: center;">Failed to load devices: ${res.error || 'Unknown error'}</div>`;
        }
    });
}

function revokeCloudDevice(id) {
    if (!confirm("Are you sure you want to revoke this device? It will be logged out and its future data won't be linked to your account.")) return;
    window.pywebview.api.revoke_cloud_device(id).then(res => {
        if (res.success) {
            loadCloudDevices();
        } else {
            alert("Revocation failed: " + res.error);
        }
    });
}
/* Library Logic */
let libraryMedia = [];
let currentLibFilter = 'all';
let libraryScanInterval = null;

window.openLibraryFolders = function() {
    const el = document.getElementById('library-folders-container');
    el.style.display = el.style.display === 'none' ? 'block' : 'none';
    if(el.style.display === 'block') window.fetchLibraryFolders();
};

window.fetchLibraryFolders = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_library_folders().then(data => {
            if(data.success) {
                const list = document.getElementById('folders-list');
                list.innerHTML = data.folders.map(f => `
                    <li style="display: flex; justify-content: space-between; background: rgba(0,0,0,0.2); padding: 8px; border-radius: 4px;">
                        <span>${f.path}</span>
                        <button onclick="removeLibraryFolder('${f.path.replace(/\\/g, '\\\\')}')" style="background: none; border: none; color: #ff4d4d; cursor: pointer;"><i class="fas fa-trash"></i></button>
                    </li>
                `).join('');
            }
        });
    }
};

window.addLibraryFolder = function() {
    const path = document.getElementById('new-folder-path').value;
    if(!path) return;
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.add_library_folder(path).then(data => {
            if(data.success) {
                document.getElementById('new-folder-path').value = '';
                window.fetchLibraryFolders();
                window.scanLibrary();
            } else {
                alert("Error: " + data.error);
            }
        });
    }
};

window.removeLibraryFolder = function(path) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.remove_library_folder(path).then(data => {
            if(data.success) window.fetchLibraryFolders();
        });
    }
};

window.forceClearRPC = function() {
    if(window.pywebview && window.pywebview.api) {
        window.pywebview.api.force_clear_rpc().then(data => {
            if(data.success) {
                window.fetchState();
            }
        });
    }
};

window.scanLibrary = function() {
    const btn = document.getElementById('btn-scan-library');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Scanning...';
    btn.disabled = true;
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.scan_library().then(() => {
            if(!libraryScanInterval) libraryScanInterval = setInterval(window.checkLibraryScan, 2000);
        });
    }
};

window.checkLibraryScan = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_library_status().then(data => {
            if(!data.is_scanning) {
                clearInterval(libraryScanInterval);
                libraryScanInterval = null;
                const btn = document.getElementById('btn-scan-library');
                btn.innerHTML = '<i class="fas fa-sync"></i> Scan';
                btn.disabled = false;
                window.fetchLibraryMedia();
            }
        });
    }
};

window.fetchLibraryMedia = function() {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.get_media_library().then(data => {
            if(data.success) {
                libraryMedia = data.media;
                window.renderLibrary();
                window.renderContinueWatching();
            }
        });
    }
};

window.setLibraryFilter = function(f) {
    currentLibFilter = f;
    document.querySelectorAll('.lib-filter-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.lib-filter-btn[data-filter="${f}"]`).classList.add('active');
    window.renderLibrary();
};

window.filterLibrary = function() {
    window.renderLibrary();
};

window.renderLibrary = function() {
    const grid = document.getElementById('library-grid');
    const search = (document.getElementById('library-search').value || '').toLowerCase();
    
    let displayList = [];
    let seriesMap = {};
    
    libraryMedia.forEach(m => {
        if(currentLibFilter !== 'all' && m.media_type !== currentLibFilter) return;
        if(search && !(m.title || '').toLowerCase().includes(search) && !(m.filename || '').toLowerCase().includes(search)) return;
        
        let isAnime = m.media_type === 'anime' || (m.anilist_id != null);
        if(isAnime && m.title) {
            let groupKey = m.anilist_id ? `al_${m.anilist_id}` : `title_${m.title}`;
            if(!seriesMap[groupKey]) {
                seriesMap[groupKey] = {...m, is_group: true, count: 1};
                displayList.push(seriesMap[groupKey]);
            } else {
                seriesMap[groupKey].count++;
            }
        } else {
            displayList.push(m);
        }
    });
    
    if(displayList.length === 0) {
        grid.innerHTML = '<p class="empty-state">No media found.</p>';
        return;
    }
    
    window.currentSeriesMap = seriesMap;
    
    grid.innerHTML = displayList.map(m => {
        const title = m.title || m.filename;
        const sub = m.is_group ? `${m.count} Episodes` : (m.episode ? `Episode ${m.episode}` : (m.media_type === 'music' ? 'Music' : 'Video'));
        const poster = m.cover_url || 'icon.png';
        const progressPct = m.watch_progress && m.duration ? Math.min(100, (m.watch_progress / m.duration) * 100) : 0;
        
        let clickAction = m.is_group ? `window.showEpisodeModal('${m.groupKey}')` : `playMedia(${m.id})`;
        
        return `
            <div class="lib-media-card" onclick="${clickAction}">
                <div class="lib-media-poster-container">
                    <img src="${poster}" class="lib-media-poster" onerror="this.src='icon.png'">
                    <div class="lib-media-overlay">
                        <i class="fas fa-${m.is_group ? 'folder-open' : 'play'} lib-media-play-icon"></i>
                    </div>
                </div>
                ${progressPct > 0 ? `<div class="lib-progress-bg"><div class="lib-progress-fill" style="width: ${progressPct}%"></div></div>` : ''}
                <div class="lib-media-info">
                    <div class="lib-media-title" title="${title.replace(/"/g, '&quot;')}">${title}</div>
                    <div class="lib-media-sub">${sub}</div>
                </div>
            </div>
        `;
    }).join('');
};

window.showEpisodeModal = function(groupKey) {
    let group = window.currentSeriesMap[groupKey];
    if(!group) return;
    
    document.getElementById('episode-modal-title').innerText = group.title || 'Select Episode';
    
    let items = group.group_items.sort((a,b) => (a.episode || 0) - (b.episode || 0));
    
    let html = items.map(m => {
        let epName = m.episode_title ? `Episode ${m.episode} - ${m.episode_title}` : (m.episode ? `Episode ${m.episode}` : m.filename);
        let progressPct = m.watch_progress && m.duration ? Math.min(100, (m.watch_progress / m.duration) * 100) : 0;
        return `
            <div onclick="playMedia(${m.id}); document.getElementById('episode-modal').style.display='none'" 
                 style="padding: 12px; border-radius: 6px; cursor: pointer; transition: background 0.2s; margin-bottom: 4px; display: flex; flex-direction: column; background: rgba(255,255,255,0.05);"
                 onmouseover="this.style.background='rgba(255,255,255,0.1)'" onmouseout="this.style.background='rgba(255,255,255,0.05)'">
                <div style="font-weight: 500;">${epName}</div>
                ${progressPct > 0 ? `<div style="height: 4px; background: rgba(255,255,255,0.1); width: 100%; border-radius: 2px; margin-top: 6px;"><div style="height: 100%; background: var(--accent-blurple); border-radius: 2px; width: ${progressPct}%"></div></div>` : ''}
            </div>
        `;
    }).join('');
    
    document.getElementById('episode-modal-list').innerHTML = html;
    document.getElementById('episode-modal').style.display = 'flex';
};

window.renderContinueWatching = function() {
    const rail = document.getElementById('continue-watching-rail');
    let cw = libraryMedia.filter(m => m.watch_progress > 0 && (!m.duration || m.watch_progress < m.duration - 60)).sort((a,b) => b.watch_progress - a.watch_progress);
    
    let seriesSeen = new Set();
    let uniqueCw = [];
    for(let m of cw) {
        let sKey = m.media_type === 'anime' ? m.title : m.id;
        if(!seriesSeen.has(sKey)) {
            seriesSeen.add(sKey);
            uniqueCw.push(m);
        }
    }
    
    uniqueCw = uniqueCw.slice(0, 10);
    
    if(uniqueCw.length === 0) {
        rail.innerHTML = '<p class="empty-state" style="margin: 0; padding: 12px;">No active shows.</p>';
        document.getElementById('continue-watching-container').style.display = 'none';
        return;
    }
    
    document.getElementById('continue-watching-container').style.display = 'block';
    
    rail.innerHTML = uniqueCw.map(m => {
        const title = m.title || m.filename;
        const sub = m.episode ? `Ep ${m.episode}` : '';
        const poster = m.cover_url || 'icon.png';
        const progressPct = m.duration ? Math.min(100, (m.watch_progress / m.duration) * 100) : 0;
        
        return `
            <div class="lib-continue-card" onclick="playMedia(${m.id})">
                <img src="${poster}" class="lib-continue-poster" onerror="this.src='icon.png'">
                <div class="lib-continue-info">
                    <div class="lib-continue-title">${title}</div>
                    <div style="font-size: 0.75rem; color: rgba(255,255,255,0.6); margin-bottom: 4px;">${sub}</div>
                    <div style="height: 4px; background: rgba(255,255,255,0.1); width: 100%; border-radius: 2px; overflow: hidden;">
                        <div style="height: 100%; background: var(--accent-blurple); width: ${progressPct}%;"></div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
};

window.playMedia = function(id) {
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.play_library_media(id).then(data => {
            if(!data.success) {
                alert("Playback failed: " + data.error);
            }
        });
    }
};

document.addEventListener('pywebviewready', () => {
    document.querySelectorAll('.nav-item').forEach(el => {
        el.addEventListener('click', (e) => {
            if(el.dataset.tab === 'tab-library') {
                window.fetchLibraryMedia();
            }
        });
    });
    
    // Auto-scan library in background on startup
    setTimeout(() => {
        window.fetchLibraryMedia();
        window.scanLibrary();
    }, 1000);
});
