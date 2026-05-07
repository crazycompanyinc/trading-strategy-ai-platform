#!/bin/bash
set -e

echo "============================================"
echo " Trading Strategy AI - Build Script"
echo "============================================"

echo ""
echo "[1/4] Installing frontend dependencies..."
cd frontend
npm ci

echo ""
echo "[2/4] Building React app..."
npx react-scripts build

echo ""
echo "[3/4] Building Electron (Windows via cross-compile)..."
# Note: Cross-compiling Windows exe from Linux requires wine
# For native Windows build, run build-windows.bat on Windows
# or use GitHub Actions (see .github/workflows/build-windows.yml)

if command -v wine &> /dev/null; then
    npx electron-builder --win nsis
    npx electron-builder --win portable
    echo ""
    echo "Build complete!"
    echo "Installer: frontend/dist/TradingStrategyAI-Setup-1.0.0.exe"
    echo "Portable:  frontend/dist/TradingStrategyAI-Portable-1.0.0.exe"
else
    echo ""
    echo "Wine not available for cross-compilation."
    echo "To build Windows .exe:"
    echo "  1. Run 'build-windows.bat' on a Windows machine, OR"
    echo "  2. Push a tag 'v1.0.0' to GitHub to trigger CI build, OR"
    echo "  3. Install wine: sudo apt install wine"
    echo ""
    echo "React build is ready in frontend/build/"
fi

cd ..
