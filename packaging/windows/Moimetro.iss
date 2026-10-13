; UTF-8 WITH BOM required: Inno Setup 6.2.2 otherwise reads accented text as ANSI.
; Build from GitHub Actions or pass /DBuildRoot=<absolute repo path>.
#ifndef BuildRoot
  #define BuildRoot "..\.."
#endif
#ifndef Arch
  #define Arch "x86"
#endif
#ifndef Flavor
  #define Flavor "legacy"
#endif
#define MyVersion "0.2.0"
#define MyAppName "Moímetro"
#define OutputName "Moimetro-Setup-" + Flavor + "-" + Arch

[Setup]
AppId={{8D2C2597-90BF-4E22-9DF6-E813C89D03F7}
AppName={#MyAppName}
AppVersion={#MyVersion}
AppVerName={#MyAppName} {#MyVersion}
VersionInfoProductName={#MyAppName}
VersionInfoDescription={#MyAppName} - Instalador
DefaultDirName={localappdata}\Programs\Moimetro
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
UsePreviousAppDir=yes
UninstallDisplayIcon={app}\Moimetro.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
OutputDir={#BuildRoot}\dist\installer
OutputBaseFilename={#OutputName}
#if Flavor == "modern"
MinVersion=6.3
#else
MinVersion=6.1sp1
#endif
#if Arch == "x64"
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
#endif

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Opciones de acceso:"; Flags: checkedonce

[Files]
Source: "{#BuildRoot}\dist\Moimetro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Remove only the corrupted shortcut names created by previous ANSI decoding
; of UTF-8. They are explicitly scoped to this application's former names.
[InstallDelete]
Type: files; Name: "{autodesktop}\\MoÃ­metro.lnk"
Type: files; Name: "{autoprograms}\\MoÃ­metro.lnk"
Type: files; Name: "{autodesktop}\\MoÃmetro.lnk"
Type: files; Name: "{autoprograms}\\MoÃmetro.lnk"

[Icons]
Name: "{autoprograms}\Moímetro"; Filename: "{app}\Moimetro.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Moímetro"; Filename: "{app}\Moimetro.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Moimetro.exe"; Description: "Iniciar Moímetro"; Flags: nowait postinstall skipifsilent
