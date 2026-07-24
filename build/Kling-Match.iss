; Inno Setup 6 script for Kling-Match
; Build: run build\build.ps1  (or manually: ISCC.exe build\Kling-Match.iss)

#define AppName      "Kling-Match"
#define AppVersion   Trim(FileRead(FileOpen("..\version.txt")))
#define AppPublisher "Lotzi-tosafix"
#define AppURL       "https://github.com/Lotzi-tosafix/Kling-Match"
#define AppExeName   "Kling-Match.exe"
#define DistDir      "..\dist\Kling-Match"

; ────────────────────────────────────────────────────────────────────
[Setup]
AppId={{B3A5C1D2-9F4E-4A7B-8E3C-2D1F6A0B9E5C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist\installer
OutputBaseFilename=Kling-Match-{#AppVersion}-setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#AppExeName}

; ────────────────────────────────────────────────────────────────────
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

; ────────────────────────────────────────────────────────────────────
[Tasks]
Name: "desktopicon";    Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"
Name: "assocklng";      Description: "Associate &.klng project files with Kling-Match"; GroupDescription: "File associations:"
Name: "assocaudio";     Description: "Associate audio files (&MP3, WAV, FLAC...) with Kling-Match"; GroupDescription: "File associations:"

; ────────────────────────────────────────────────────────────────────
[Files]
; Main application files
Source: "{#DistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; install_type marker — written so the auto-updater knows this is an installer build
Source: "install_type_installer.txt"; DestName: "install_type.txt"; DestDir: "{app}"; Flags: ignoreversion

; ────────────────────────────────────────────────────────────────────
[Icons]
Name: "{group}\{#AppName}";             Filename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}";   Filename: "{uninstallexe}"
Name: "{commondesktop}\{#AppName}";     Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Check: IsAdminInstallMode
Name: "{userdesktop}\{#AppName}";       Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; Check: not IsAdminInstallMode

; ────────────────────────────────────────────────────────────────────
; .klng file association
[Registry]
; ── .klng extension ──────────────────────────────────────────────────
Root: HKA; Subkey: "Software\Classes\.klng";                                  ValueType: string; ValueName: ""; ValueData: "KlingMatch.Project"; Flags: uninsdeletevalue; Tasks: assocklng
Root: HKA; Subkey: "Software\Classes\.klng";                                  ValueType: string; ValueName: "Content Type"; ValueData: "application/x-kling-match"; Flags: uninsdeletevalue; Tasks: assocklng
Root: HKA; Subkey: "Software\Classes\KlingMatch.Project";                     ValueType: string; ValueName: ""; ValueData: "Kling-Match Project"; Flags: uninsdeletevalue uninsdeletekeyifempty; Tasks: assocklng
Root: HKA; Subkey: "Software\Classes\KlingMatch.Project\DefaultIcon";         ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExeName},0"; Flags: uninsdeletevalue; Tasks: assocklng
Root: HKA; Subkey: "Software\Classes\KlingMatch.Project\shell\open\command";  ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Flags: uninsdeletevalue; Tasks: assocklng

; ── Audio file associations (optional, user-choice) ─────────────────
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids";  ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids";  ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids";  ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids";  ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids";  ValueType: string; ValueName: "KlingMatch.AudioFile"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\KlingMatch.AudioFile";                    ValueType: string; ValueName: ""; ValueData: "Audio File"; Flags: uninsdeletevalue uninsdeletekeyifempty; Tasks: assocaudio
Root: HKA; Subkey: "Software\Classes\KlingMatch.AudioFile\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Flags: uninsdeletevalue; Tasks: assocaudio

; Notify Windows shell to refresh icons
Root: HKA; Subkey: "Software\Classes\.klng"; ValueType: string; ValueName: ""; ValueData: "KlingMatch.Project"; Tasks: assocklng

; ────────────────────────────────────────────────────────────────────
[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

; ────────────────────────────────────────────────────────────────────
[Code]
// Refresh Windows shell icon cache after install so .klng icons appear immediately
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    RegWriteStringValue(HKA, 'Software\Classes\.klng', '', 'KlingMatch.Project');
end;
