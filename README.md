<div align="center">
  <img src="https://upload.wikimedia.org/wikipedia/commons/3/38/VLC_icon.png" alt="VLC Media Player" width="100"/>
  <h1>VLC Discord RPC</h1>
  <p><strong>A beautiful, autonomous Rich Presence client for VLC Media Player with AI-powered title detection.</strong></p>
</div>

<br>

VLC RPC seamlessly connects your VLC Media Player to Discord. Show your friends exactly what you are watching or listening to, automatically parse complex file names into clean movie titles, and track your media history via a sleek, modern desktop dashboard.

## ✨ Features
*   **Intelligent Parsing**: Built-in AI (`GuessIt`) automatically detects Movies and TV Shows from raw file names, stripping away scene tags (`1080p`, `x264`, `BluRay`) to display clean titles (e.g., *The Matrix (1999)*).
*   **Universal Out-of-the-Box**: Uses the official VLC Discord application ID. No need to create your own Discord developer apps or set up client IDs!
*   **Live History Tracking**: A modern UI dashboard built with WebViews tracks your complete watch history locally. 
*   **Media Artwork**: Automatically fetches high-quality movie/show posters and Wiki thumbnails to display on your Discord profile.
*   **Lightweight & Secure**: Uses thread-safe architecture with less than 50MB RAM footprint. Minimizes to your system tray out of sight.

## 🚀 Installation

### Option 1: Quick Installer (Recommended for Windows)
1. Go to the [Releases Tab](https://github.com/DulinNethmira/VLC-RPC/releases/tag/v1.0.0).
2. Download `VLC RPC Setup.exe` from the latest release.
3. Run the installer. It will automatically create a desktop shortcut and configure everything.

### Option 2: Run from Source
If you prefer to run the python script directly:
```bash
git clone https://github.com/YOUR_USERNAME/YOUR_REPO.git
cd YOUR_REPO
pip install -r requirements.txt
python vlc_discord_rpc_gui.py
```

## ⚙️ How to Configure VLC
For this tool to read your media data, you must enable the VLC Web Interface:
1. Open **VLC Media Player**.
2. Go to **Tools** > **Preferences** (or press `Ctrl+P`).
3. At the bottom left, under **Show settings**, click **All**.
4. In the left menu, go to **Interface** > **Main interfaces** and check the box for **Web**.
5. Expand **Main interfaces**, click on **Lua**, and under *Lua HTTP*, set a **Password** (e.g., `1234`).
6. Click **Save** and restart VLC.
7. Open the VLC RPC Dashboard from your system tray, go to **Settings**, and enter that same password.

## 🛠️ Building the Installer
To compile the Python application into a standalone Windows installer yourself:
1. Install `PyInstaller` and build the executable:
   ```bash
   pyinstaller --noconfirm --name "VLC RPC" --onedir --windowed --icon "web/icon.ico" --add-data "web;web" --collect-data babelfish --collect-data guessit "vlc_discord_rpc_gui.py"
   ```
2. Compile the `setup.iss` file using **Inno Setup 6** to generate the final setup executable.

## 📜 License
This project is open-source and available under the MIT License.
