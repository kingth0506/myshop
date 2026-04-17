#!/bin/bash
set -e
cd "$(dirname "$0")"
echo "===== MYSHOP Mac Build ====="

git pull origin main

echo "[1] PyInstaller 빌드..."
python3 -m PyInstaller myshop_mac.spec --noconfirm --clean

echo "[2] ZIP 생성..."
cd dist
zip -r ../MYSHOP_Mac.zip MYSHOP.app
cd ..

echo "[3] 버전 추출..."
VER=$(python3 -c "import re; print(re.search(r'VER\s*=\s*\"(.+?)\"', open('main.py').read()).group(1))")
echo "버전: v$VER"

echo "[4] GitHub Release..."
gh release create "v$VER" --title "v$VER" --notes "v$VER 업데이트" 2>/dev/null || true
gh release upload "v$VER" MYSHOP_Mac.zip --clobber

echo "[5] 완료!"
