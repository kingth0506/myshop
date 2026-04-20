@echo off
chcp 65001 >nul
echo ===== ORDERMASTER Windows Build =====

cd /d "%~dp0"
git pull origin main

echo [1] PyInstaller 빌드...
python -m PyInstaller myshop_win.spec --noconfirm --clean

echo [2] Inno Setup 설치파일 생성...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" setup.iss

echo [3] 버전 추출...
for /f "tokens=2 delims='""'" %%a in ('findstr /C:"VER = " main.py') do set VER=%%a
echo 버전: v%VER%

echo [4] GitHub Release 업로드...
gh release create v%VER% --title "v%VER%" --notes "v%VER% 업데이트" 2>nul
gh release upload v%VER% installer\ORDERMASTER_Install.exe --clobber

echo [5] 완료!
pause
