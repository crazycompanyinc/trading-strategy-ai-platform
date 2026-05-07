@echo off
echo ============================================
echo Trading Strategy AI - Windows Build Script
echo ============================================

echo.
echo [1/4] Installing frontend dependencies...
cd frontend
call npm ci
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
echo [3/4] Building Electron NSIS installer...
call npx electron-builder --win nsis
if %ERRORLEVEL% neq 0 (
    echo ERROR: Electron build failed
    exit /b 1
)

echo.
echo [4/4] Building portable version...
call npx electron-builder --win portable

echo.
echo ============================================
echo Build complete!
echo.
echo Installer: frontend\dist\TradingStrategyAI-Setup-1.0.0.exe
echo Portable:  frontend\dist\TradingStrategyAI-Portable-1.0.0.exe
echo ============================================

cd ..
pause
