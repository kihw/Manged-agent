#define MyAppName "Managed Agent"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Managed Agent"
#define MyAppExeName "Managed Agent.exe"

[Setup]
AppId={{C6AE45F2-4F1D-48F7-B6A0-ED444F687A9B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Managed Agent
DefaultGroupName=Managed Agent
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
OutputDir={#SourcePath}\..\..\artifacts\windows
OutputBaseFilename=ManagedAgentSetup

[Files]
Source: "{#SourcePath}\..\..\dist\Managed Agent\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Managed Agent"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall Managed Agent"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Managed Agent"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Managed Agent"; Flags: nowait postinstall skipifsilent
