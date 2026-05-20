; ============================================================================
;  InstalockValorant — Inno Setup Script
;  Gera um instalador profissional .exe para Windows
;  Download Inno Setup: https://jrsoftware.org/isdl.php
; ============================================================================

#define AppName      "InstalockValorant"
#define AppVersion   "1.1.0"
#define AppPublisher "DevAlex-full"
#define AppURL       "https://instalockvalorant.vercel.app"
#define AppExeName   "InstalockValorant.exe"
#define AppGUID      "{{A7B3C2D1-4E5F-6789-ABCD-EF0123456789}"

[Setup]
AppId={#AppGUID}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} v{#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
AppUpdatesURL=https://github.com/DevAlex-full/InstalockValorant/releases

; Instala sem precisar de admin
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Diretório de instalação
DefaultDirName={localappdata}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes

; Saída
OutputDir=..\dist
OutputBaseFilename=InstalockValorant-v{#AppVersion}-Setup
SetupIconFile=..\assets\instalock_logo.ico

; Compressão máxima
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes

; Visual
WizardStyle=modern
WizardSizePercent=120
ShowLanguageDialog=no

; Configs extras
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName} v{#AppVersion}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription=Instalock automatico para Valorant
VersionInfoProductName={#AppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon";  Description: "Criar atalho na Area de Trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked
Name: "startupicon";  Description: "Iniciar com o Windows";             GroupDescription: "Opcoes:";  Flags: unchecked

[Files]
Source: "..\{#AppExeName}";   DestDir: "{app}"; Flags: ignoreversion
Source: "..\assets\*";        DestDir: "{app}\assets"; Flags: ignoreversion recursesubdirs

[Icons]
Name: "{group}\{#AppName}";               Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\instalock_logo.ico"
Name: "{group}\Desinstalar {#AppName}";   Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";         Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\assets\instalock_logo.ico"; Tasks: desktopicon
Name: "{autostartup}\{#AppName}";         Filename: "{app}\{#AppExeName}"; Tasks: startupicon

[Registry]
Root: HKCU; Subkey: "Software\{#AppPublisher}\{#AppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#AppVersion}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Abrir {#AppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{localappdata}\InstalockValorant\config.json"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not DirExists(ExpandConstant('{localappdata}\Riot Games')) then
  begin
    if MsgBox(
      'Valorant nao foi detectado neste computador.' + #13#10 +
      'O InstalockValorant requer o Valorant para funcionar.' + #13#10#13#10 +
      'Deseja continuar mesmo assim?',
      mbConfirmation, MB_YESNO) = IDNO then
      Result := False;
  end;
end;
