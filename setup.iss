[Setup]
AppName=VLC RPC
AppVersion=3.4
DefaultDirName={pf}\VLC RPC
DefaultGroupName=VLC RPC
OutputDir=dist
OutputBaseFilename=VLC RPC Setup
SetupIconFile=web\icon.ico
UninstallDisplayIcon={app}\vlc_discord_rpc_gui.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\vlc_discord_rpc_gui\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VLC RPC"; Filename: "{app}\vlc_discord_rpc_gui.exe"
Name: "{autodesktop}\VLC RPC"; Filename: "{app}\vlc_discord_rpc_gui.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\vlc_discord_rpc_gui.exe"; Description: "{cm:LaunchProgram,VLC RPC}"; Flags: nowait postinstall skipifsilent
