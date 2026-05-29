[Setup]
AppName=VLC RPC
AppVersion=1.0.0
DefaultDirName={pf}\VLC RPC
DefaultGroupName=VLC RPC
OutputDir=dist
OutputBaseFilename=VLC RPC Setup
SetupIconFile=web\icon.ico
UninstallDisplayIcon={app}\VLC RPC.exe
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\VLC RPC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VLC RPC"; Filename: "{app}\VLC RPC.exe"
Name: "{autodesktop}\VLC RPC"; Filename: "{app}\VLC RPC.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\VLC RPC.exe"; Description: "{cm:LaunchProgram,VLC RPC}"; Flags: nowait postinstall skipifsilent
