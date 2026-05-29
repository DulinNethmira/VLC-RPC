@echo off
title VLC Discord Rich Presence GUI
cd /d "%~dp0"
if not exist venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found! Run the installation first.
    pause
    exit /b
)
echo Starting VLC Discord RPC (Vaporwave GUI)...
start /b venv\Scripts\pythonw.exe vlc_discord_rpc_gui.py
exit
