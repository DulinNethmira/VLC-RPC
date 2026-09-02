<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:8b5cf6&height=250&section=header&text=VLC%20Discord%20RPC&fontSize=70&fontColor=ffffff&animation=twinkling&desc=The%20Ultimate%20Media%20Companion&descAlignY=76&descAlign=62" width="100%" />

  <img src="https://readme-typing-svg.demolab.com?font=Outfit&size=20&pause=1000&color=8B5CF6&center=true&vCenter=true&width=600&lines=Discord+Rich+Presence+for+VLC;Auto-Track+Anime+on+AniList;Fully+Offline+Local+Media+Library;Advanced+Analytics+%26+Dashboard;The+Ultimate+Media+Companion" alt="Typing SVG" />

  <br>

  <a href="https://github.com/DulinNethmira/VLC-RPC/releases/latest"><img src="https://img.shields.io/github/v/release/DulinNethmira/VLC-RPC?style=for-the-badge&color=8B5CF6&logo=github&logoColor=white" alt="Release"/></a>
  <a href="https://github.com/DulinNethmira/VLC-RPC/blob/main/LICENSE"><img src="https://img.shields.io/github/license/DulinNethmira/VLC-RPC?style=for-the-badge&color=6366F1&logo=open-source-initiative&logoColor=white" alt="License"/></a>
  <a href="https://github.com/DulinNethmira/VLC-RPC/releases/latest"><img src="https://img.shields.io/github/downloads/DulinNethmira/VLC-RPC/total?style=for-the-badge&color=34D399&logo=docusign&logoColor=white" alt="Downloads"/></a>
  
  <br><br>
  
  <a href="https://skillicons.dev">
    <img src="https://skillicons.dev/icons?i=python,html,css,js,sqlite,discord,github" />
  </a>
</div>

<br>

VLC RPC seamlessly connects your VLC Media Player to Discord. It shows your friends exactly what you're watching or listening to, automatically syncs your anime progress to AniList, and tracks your entire media history in a sleek desktop dashboard.

---

## ✨ Cutting-Edge Features

<details open>
  <summary><b>📺 AniList Integration (Smart Sync)</b></summary>
  <br>
  
  - **Secure OAuth 2.0** — Full Authorization Code Flow with a local callback server. Your credentials never leave your machine.
  - **Auto Episode Sync** — Automatically updates your AniList progress when you cross a configurable watch threshold (default: 80%).
  - **Auto-Score Popups** — Automatically prompts you to rate a series the moment you finish the final episode, matched to your AniList preference format.
  - **AniSkip Integration** — Automatically skips Openings (OP) and Endings (ED) if you're watching the correct episode based on AniList data.
  - **Smart Matching** — 2-tier search: checks your active AniList list first, then falls back to global database search with format validation.
  - **Real-time AniList Logs** — Dedicated in-app log panel shows every sync decision with color-coded entries for debugging.
</details>

<details open>
  <summary><b>📊 Next-Gen Dashboard & Analytics</b></summary>
  <br>
  
  - **Anime Wrapped (Analytics)** — Generate and download a beautiful image of your "Anime Wrap" directly from the Analytics tab to share with your friends. Features deep stats like Average Session Length, Most Binge-Watched Day, and Total Hours!
  - **Custom Accent Themes** — Choose from a variety of modern UI accent themes in Preferences to match your aesthetic (Discord Blurple, Ruby Red, Emerald Green, Neon Purple, etc).
  - **Modern WebView UI** — Beautiful glassmorphism design with ambient glow effects, 3D hover animations, and built with the modern Outfit font family.
  - **Live Discord Preview & Toggle** — See exactly how your rich presence will look on Discord inside the app in real-time. Instantly toggle your Discord Activity ON/OFF directly from the Dashboard with a single click.
  - **macOS-Style Toasts** — Elegant, animated dark-mode toast notifications for app events!
</details>

<details open>
  <summary><b>📁 Local Media Library</b></summary>
  <br>
  
  - **Offline Media Management** — Add folders and let the background scanner seamlessly organize your Anime, Movies, TV Shows, and Music without requiring an internet connection.
  - **Smart Continue Watching** — Uses identity-based progress mapping to place unfinished episodes right on your dashboard.
  - **One-Click Playback** — Instantly launch any local file directly into your active VLC player with perfect Unicode path handling.
</details>

<details open>
  <summary><b>🎯 Core Engine & Parsing</b></summary>
  <br>
  
  - **Gemini AI Title Parsing** — Optional integration with Google Gemini AI API to extract perfect titles and episode numbers from extremely messy, abbreviated, or non-standard video filenames that standard parsers fail on.
  - **Smart Title Parsing** — Built-in `GuessIt` engine strips scene tags (`1080p`, `x264`, `BluRay`) to display clean titles like *The Matrix (1999)* or *One Piece Episode 1168*.
  - **Universal Out-of-the-Box** — Uses the official VLC Discord application ID. No need to create Discord developer apps or set up client IDs.
</details>

<details open>
  <summary><b>📡 Rich Discord Presence</b></summary>
  <br>
  
  - **Live Scene Snapshots** — Takes a live frame capture from your local video (Anime/Movies) using FFmpeg and uploads it to display as the rich presence cover art instead of generic posters.
  - **Media Artwork** — Fetches high-quality posters from OMDb, Jikan (MyAnimeList), TVmaze, iTunes, and Wikipedia (when Snapshots are disabled).
  - **Interactive Buttons** — Adds clickable AniList/IMDb links directly on your Discord profile when available.
</details>

---

## 🚀 Quick Start Guide

<details>
  <summary><b>Option 1: Quick Installer (Recommended)</b></summary>
  <br>
  
  1. Go to the <a href="https://github.com/DulinNethmira/VLC-RPC/releases/latest"><b>Latest Release</b></a>.
  2. Download <b><code>VLC RPC Setup.exe</code></b>.
  3. Run the installer — it creates a desktop shortcut and configures everything automatically.
</details>

<details>
  <summary><b>Option 2: Run from Source</b></summary>
  <br>
  
  ```bash
  git clone https://github.com/DulinNethmira/VLC-RPC.git
  cd VLC-RPC
  pip install -r requirements.txt
  python vlc_discord_rpc_gui.py
  ```
</details>

---

## ⚙️ Integrations Setup

<details>
  <summary><b>VLC Media Player Setup (Required)</b></summary>
  <br>
  
  For the tool to read your media data, enable the VLC Web Interface:
  1. Open **VLC Media Player**.
  2. Go to **Tools** > **Preferences** (or press `Ctrl+P`).
  3. At the bottom left, under **Show settings**, select **All**.
  4. Navigate to **Interface** > **Main interfaces** and check the **Web** checkbox.
  5. Expand **Main interfaces**, click **Lua**, and under *Lua HTTP*, set a **Password** (e.g., `1234`).
  6. Click **Save** and **restart VLC**.
  7. Open the VLC RPC Dashboard, go to **Preferences**, and enter that same password.
</details>

<details>
  <summary><b>AniList Setup (Optional)</b></summary>
  <br>
  
  To enable automatic anime episode syncing:
  1. Go to <a href="https://anilist.co/settings/developer">AniList Developer Settings</a> and create a new API v2 Client.
  2. Set the **Redirect URI** to `http://localhost:8899`.
  3. Copy your **Client ID** and **Client Secret**.
  4. In the VLC RPC Dashboard, go to **Integrations** and paste both values.
  5. Click **Connect AniList Account** — a browser window opens for you to authorize.
  6. Once connected, the button turns green. Your anime progress will sync automatically!
</details>

---

<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=0:6366f1,100:8b5cf6&height=100&section=footer" width="100%" />
</div>
