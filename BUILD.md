# Building the Windows .exe

This project uses **electron-builder** to create Windows installers. Since electron-builder requires Windows to build Windows executables, there are several options:

## Option 1: GitHub Actions (Easiest - Recommended)

The `.github/workflows/build-windows.yml` workflow automatically builds the Windows installer when you push a tag:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Then check the **Actions** tab on GitHub and download the .exe from the **Releases** page.

## Option 2: Build on Your Windows Machine

### Prerequisites
- [Node.js 20+](https://nodejs.org/)
- [Python 3.12+](https://python.org/)

### Steps

1. **Clone the repo:**
   ```cmd
   git clone https://github.com/crazycompanyinc/trading-strategy-ai-platform.git
   cd trading-strategy-ai-platform
   ```

2. **Run the build script:**
   ```cmd
   build-windows.bat
   ```

   Or manually:
   ```cmd
   cd frontend
   npm install --legacy-peer-deps
   npx react-scripts build
   npx electron-builder --win nsis
   ```

3. **Find your build:**
   - Installer: `frontend\dist\TradingStrategyAI-Setup-1.0.0.exe`
   - Portable: `frontend\dist\TradingStrategyAI-Portable-1.0.0.exe`

## Option 3: Build from Linux/Mac with Wine

```bash
sudo apt install wine wine64
./build.sh
```

## Output

| File | Description |
|------|-------------|
| `TradingStrategyAI-Setup-x.x.x.exe` | NSIS installer (recommended) - guides user through installation |
| `TradingStrategyAI-Portable-x.x.x.exe` | Portable version - no install needed, just run |

## Troubleshooting

- **npm install fails**: Use `npm install --legacy-peer-deps`
- **electron-builder fails**: Make sure the React build ran first (`npx react-scripts build`)
- **Missing icon**: The icon.png is auto-generated. Replace it with a proper 256x256 icon for production.
