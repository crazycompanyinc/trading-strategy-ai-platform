# Trading Strategy AI Platform

AI-powered desktop platform for trading strategy research via natural language. Chat with an AI agent that understands your trading ideas, backtests them, mutates them to find better variants, and generates MT5 Expert Advisor code.

## Download

### Windows Portable (No Install Required)
**[Download TradingStrategyAI-Portable-1.0.0.exe](https://github.com/crazycompanyinc/trading-strategy-ai-platform/releases/download/v1.0.0/TradingStrategyAI-Portable-1.0.0.exe)** (75 MB)

Just download and run! No installation needed.

### Build Installer from Source

For the full NSIS installer with shortcuts and uninstaller:
```cmd
git clone https://github.com/crazycompanyinc/trading-strategy-ai-platform.git
cd trading-strategy-ai-platform
build-windows.bat
```
Output: `frontend\dist\TradingStrategyAI-Setup-1.0.0.exe`

## Features

- **Natural Language to Strategy**: Describe your trading idea in plain English or Spanish
- **Image Upload**: Drag & drop charts/screenshots for AI analysis
- **Automated Backtesting**: 25+ metrics (Sharpe, Sortino, Calmar, Omega, etc.)
- **Genetic Mutation**: Evolves strategies via genetic algorithms
- **Robustness Testing**: Monte Carlo, walk-forward, sensitivity analysis, overfitting detection
- **MT5 Code Export**: Generates complete, compilable MQL5 Expert Advisor code
- **HTML Reports**: Beautiful reports with equity curves and trade logs

## Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```
Runs on http://localhost:8000

### Frontend (Development)
```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Architecture

- **Backend**: Python, FastAPI, NumPy, Pandas, Pydantic
- **Frontend**: Electron, React 18, TypeScript, TailwindCSS, Recharts, Zustand
- **Build**: electron-builder (NSIS installer + portable)
- **CI/CD**: GitHub Actions

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend API | FastAPI, WebSocket |
| Strategy Engine | Custom (backtrader-like) |
| Mutation Engine | Genetic algorithms (DEAP-style) |
| MT5 Generator | MQL5 codegen |
| Desktop App | Electron 32 + React 18 |
| State Management | Zustand |
| Charts | Recharts |
| Styling | TailwindCSS |

## License

MIT
