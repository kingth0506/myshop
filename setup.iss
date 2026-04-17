[Setup]
AppName=MYSHOP 주문관리
AppVersion=1.0.0
DefaultDirName={autopf}\MYSHOP
DefaultGroupName=MYSHOP
OutputDir=installer
OutputBaseFilename=MyShop_Install
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
Source: "dist\MYSHOP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\MYSHOP 주문관리"; Filename: "{app}\MYSHOP.exe"
Name: "{autodesktop}\MYSHOP 주문관리"; Filename: "{app}\MYSHOP.exe"

[Run]
Filename: "{app}\MYSHOP.exe"; Description: "MYSHOP 실행"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssInstall then
  begin
    Exec('powershell.exe', '-Command "Get-Process MYSHOP -ErrorAction SilentlyContinue | Stop-Process -Force"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  end;
end;
