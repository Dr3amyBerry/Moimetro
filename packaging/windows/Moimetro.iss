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
DefaultDirName={localappdata}\Programs\Moimetro
DefaultGroupName=Moímetro
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

[Icons]
Name: "{autoprograms}\Moímetro"; Filename: "{app}\Moimetro.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Moímetro"; Filename: "{app}\Moimetro.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\Moimetro.exe"; Description: "Iniciar Moímetro"; Flags: nowait postinstall skipifsilent
