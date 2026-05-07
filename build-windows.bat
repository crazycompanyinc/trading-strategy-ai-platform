@echo off
echo ============================================
echo Trading Strategy AI - Windows Build Script
echo ============================================

echo.
echo [1/4] Installing frontend dependencies...
cd frontend
call npm install --legacy-peer-deps --no-audit --no-fund
if %ERRORLEVEL% neq 0 (
    echo ERROR: npm install failed
    exit /b 1
)

echo.
echo [2/4] Building React app...
call npx react-scripts build
if %ERRORLEVEL% neq 0 (
    echo ERROR: React build failed
    exit /b 1
)

echo.
echo [3/4] Building Electron portable .exe...
call npx electron-builder --win portable
if %ERRORLEVEL% neq 0 (
    echo ERROR: Electron build failed
    exit /b 1
)

echo.
echo [4/4] Building NSIS installer...
call npx electron-builder --win nsis

echo.
echo ============================================
echo Build complete!
echo.
echo Portable:  frontend\dist\TradingStrategyAI-Portable-1.0.0.exe
echo Installer: frontend\dist\TradingStrategyAI-Setup-1.0.0.exe
echo ============================================

cd ..
pause
