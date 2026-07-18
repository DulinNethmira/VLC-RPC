<div align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/3/38/VLC_icon.png" alt="VLC Media Player" width="100"/>
  <h1>VLC Discord RPC</h1>
  <p><strong>The ultimate media companion — Discord Rich Presence, AniList auto-tracking, and a beautiful dashboard for VLC Media Player.</strong></p>
  <br>
  <a href="https://github.com/DulinNethmira/VLC-RPC/releases/latest"><img src="https://img.shields.io/github/v/release/DulinNethmira/VLC-RPC?style=for-the-badge&color=blueviolet" alt="Release"/></a>
  <a href="https://github.com/DulinNethmira/VLC-RPC/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DulinNethmira/VLC-RPC?style=for-the-badge" alt="License"/></a>
  <a href="https://github.com/DulinNethmira/VLC-RPC/releases/latest"><img src="https://img.shields.io/github/downloads/DulinNethmira/VLC-RPC/total?style=for-the-badge&color=green" alt="Downloads"/></a>
</div>

<br>

VLC RPC seamlessly connects your VLC Media Player to Discord. It shows your friends exactly what you're watching or listening to, automatically syncs your anime progress to AniList, and tracks your entire media history in a sleek desktop dashboard.

---

## ✨ Features

### 🎯 Core Engine
- **Smart Title Parsing** — Built-in `GuessIt` engine strips scene tags (`1080p`, `x264`, `BluRay`, `YIFY`) to display clean titles like *The Matrix (1999)* or *One Piece Episode 1168*.
- **Universal Out-of-the-Box** — Uses the official VLC Discord application ID. No need to create Discord developer apps or set up client IDs.
- **Media Type Detection** — Automatically classifies content as **Anime**, **Movie**, **TV Show**, or **Music** and routes to the appropriate metadata provider.

### 📡 Rich Discord Presence
- **Dynamic Status** — Shows "Watching", "Listening", or "Paused" with live progress bars and timestamps.
- **Media Artwork** — Fetches high-quality posters from OMDb, Jikan (MyAnimeList), TVmaze, iTunes, and Wikipedia.
- **Interactive Buttons** — Adds clickable AniList/IMDb links directly on your Discord profile when available.
- **Codec Badges** — Displays quality tags (4K, 1080p, HDR) and multi-audio track indicators.

### 📺 AniList Integration
- **Secure OAuth 2.0** — Full Authorization Code Flow with a local callback server. Your credentials never leave your machine.
- **Auto Episode Sync** — Automatically updates your AniList progress when you cross a configurable watch threshold (default: 80%).
- **Smart Matching** — 2-tier search: checks your active AniList list first, then falls back to global database search with format validation.
- **Real-time AniList Logs** — Dedicated in-app log panel shows every sync decision with color-coded entries for debugging.

### 🖥️ Dashboard & Tracking
- **Modern WebView UI** — Beautiful glassmorphism design with ambient glow effects, built with the Outfit font family.
- **Live Watch History** — SQLite-backed history with live "Now Playing" indicator and total watch time stats.
- **System Tray** — Minimizes to tray with startup-on-boot option. Less than 50MB RAM footprint.
- **Low-End CPU Hibernation** — Automatically enters a 12-second idle poll when VLC is closed, conserving resources.

---

## 🚀 Installation

### Option 1: Quick Installer (Recommended)
1. Go to the [**Latest Release**](https://github.com/DulinNethmira/VLC-RPC/releases/latest).
2. Download **`VLC RPC Setup.exe`**.
3. Run the installer — it creates a desktop shortcut and configures everything automatically.

### Option 2: Run from Source
```bash
git clone https://github.com/DulinNethmira/VLC-RPC.git
cd VLC-RPC
pip install -r requirements.txt
python vlc_discord_rpc_gui.py
```

---

## ⚙️ VLC Setup (Required)

For the tool to read your media data, enable the VLC Web Interface:

1. Open **VLC Media Player**.
2. Go to **Tools** > **Preferences** (or press `Ctrl+P`).
3. At the bottom left, under **Show settings**, select **All**.
4. Navigate to **Interface** > **Main interfaces** and check the **Web** checkbox.
5. Expand **Main interfaces**, click **Lua**, and under *Lua HTTP*, set a **Password** (e.g., `1234`).
6. Click **Save** and **restart VLC**.
7. Open the VLC RPC Dashboard, go to **Preferences**, and enter that same password.

---

## 📺 AniList Setup

To enable automatic anime episode syncing:

1. Go to [AniList Developer Settings](https://anilist.co/settings/developer) and create a new API v2 Client.
2. Set the **Redirect URI** to `http://localhost:8899`.
3. Copy your **Client ID** and **Client Secret**.
4. In the VLC RPC Dashboard, go to **Integrations** and paste both values.
5. Click **Connect AniList Account** — a browser window opens for you to authorize.
6. Once connected, the button turns green. Your anime progress will sync automatically!

> **Tip:** Open the **AniList Logs** tab in the sidebar to watch the sync engine in real-time.

---

## 🛠️ Building the Installer

To compile from source into a standalone Windows installer:

1. Build the executable with PyInstaller:
   ```bash
   pyinstaller --noconfirm --name "VLC RPC" --onedir --windowed --icon "web/icon.ico" --add-data "web;web" --collect-data babelfish --collect-data guessit "vlc_discord_rpc_gui.py"
   ```
2. Compile `setup.iss` with [**Inno Setup 6**](https://jrsoftware.org/isdl.php) to generate the final setup executable.

---

## 🏗️ Tech Stack

| Component | Technology |
|---|---|
| Backend | Python 3.10, `requests`, `guessit`, `pypresence` |
| UI Framework | `pywebview` (Chromium-based WebView) |
| Frontend | HTML/CSS/JS with Outfit font, Font Awesome icons |
| Database | SQLite (watch history) |
| APIs | AniList GraphQL, OMDb, Jikan, TVmaze, iTunes, Wikipedia |
| Installer | PyInstaller + Inno Setup 6 |

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
