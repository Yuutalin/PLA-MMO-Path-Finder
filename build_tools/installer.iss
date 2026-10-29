#ifndef AppVersion
  #define AppVersion "0.7.3"
#endif
#ifndef SetupLanguageFile
  #define SetupLanguageFile "compiler:Languages\ChineseSimplified.isl"
#endif
#ifndef SetupLanguageName
  #define SetupLanguageName "chinesesimp"
#endif
#ifndef SourceDir
  #define SourceDir "..\output\portable\PLA MMO Path Finder"
#endif
#ifndef OutputDir
  #define OutputDir "..\output"
#endif
#ifndef AppIcon
  #define AppIcon "default_app.ico"
#endif

#define AppName "PLA MMO Path Finder"
#define AppExeName "PLA MMO Path Finder.exe"

[Setup]
AppId={{8CFCF13D-8D0B-4A36-9D89-0C89D2F7A070}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=君粒&GPT
DefaultDirName={localappdata}\Programs\PLA MMO Path Finder
DefaultGroupName=PLA MMO Path Finder
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
OutputDir={#OutputDir}
OutputBaseFilename=PLA-MMO-Path-Finder-v{#AppVersion}-setup
SetupIconFile={#AppIcon}
UninstallDisplayIcon={app}\{#AppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
VersionInfoVersion={#AppVersion}.0
VersionInfoCompany=君粒&GPT
VersionInfoDescription=PLA MMO Path Finder Installer
VersionInfoProductName=PLA MMO Path Finder
VersionInfoProductVersion={#AppVersion}

[Languages]
Name: "{#SetupLanguageName}"; MessagesFile: "{#SetupLanguageFile}"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\PLA MMO Path Finder"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\PLA MMO Path Finder"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "启动 PLA MMO Path Finder"; Flags: postinstall nowait skipifsilent
