[Setup]
AppName=ORDERMASTER 주문관리
AppVersion=1.0.2
DefaultDirName={autopf}\ORDERMASTER
DefaultGroupName=ORDERMASTER
OutputDir=installer
OutputBaseFilename=ORDERMASTER_Install
Compression=lzma2
SolidCompression=yes
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\icon.ico
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"

[Files]
Source: "dist\ORDERMASTER\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ORDERMASTER 주문관리"; Filename: "{app}\ORDERMASTER.exe"
Name: "{autodesktop}\ORDERMASTER 주문관리"; Filename: "{app}\ORDERMASTER.exe"

[Run]
Filename: "{app}\ORDERMASTER.exe"; Description: "ORDERMASTER 실행"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('powershell.exe', '-Command "Get-Process ORDERMASTER -ErrorAction SilentlyContinue | Stop-Process -Force"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
