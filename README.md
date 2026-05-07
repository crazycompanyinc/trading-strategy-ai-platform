# Trading Strategy AI Platform

AI-powered desktop platform for trading strategy research via natural language. Chat with an AI agent that understands your trading ideas, backtests them, mutates them to find better variants, and generates MT5 Expert Advisor code.

## Features

- **Natural Language → Strategy**: Describe your trading idea in plain English (or Spanish!) and get a structured trading strategy
- **Image Analysis**: Upload charts, screenshots, or hand-drawn diagrams to complement your explanation
- **Automated Backtesting**: Executes strategies on data with comprehensive metrics (Sharpe, Sortino, Calmar, Omega, etc.)
- **Genetic Mutation**: Evolves your strategy using genetic algorithms to find more profitable variants
- **Robustness Testing**: Monte Carlo simulation, walk-forward analysis, sensitivity analysis, overfitting detection
- **MT5 Code Export**: Generates complete, compilable MQL5 Expert Advisor code
- **Beautiful Reports**: HTML reports with equity curves, trade logs, and metric dashboards

## Architecture

```
trading-strategy-ai-platform/
├── backend/
│   ├── agent/           # NLP trading agent
│   ├── strategy/        # Strategy IR models + parser
│   ├── backtester/      # Backtesting engine
│   ├── mutator/         # Genetic mutation engine
│   ├── mt5/             # MQL5 code generator
│   ├── reports/         # HTML report generator
│   ├── api/             # FastAPI routes
│   └── tests/           # Test suite
├── frontend/
│   ├── electron/        # Electron main process
│   ├── src/
│   │   ├── components/  # React components
│   │   ├── stores/      # Zustand state management
│   │   ├── types/       # TypeScript types
│   │   └── utils/       # API client
│   └── public/          # Static assets
└── docs/                # Documentation
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
python main.py
```

Backend runs on http://localhost:8000

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Process natural language trading idea |
| `/api/backtest` | POST | Run backtest for a strategy |
| `/api/mutate` | POST | Evolve strategy via genetic algorithm |
| `/api/robustness` | POST | Run robustness tests |
| `/api/export/mt5` | POST | Generate MQL5 code |
| `/api/report` | POST | Generate HTML report |
| `/ws/{session_id}` | WebSocket | Real-time streaming chat |

## Backtest Metrics

The platform calculates 25+ metrics including:

- Total Return, Sharpe Ratio, Sortino Ratio
- Max Drawdown, Calmar Ratio, Omega Ratio
- Win Rate, Profit Factor, Expectancy
- Recovery Factor, Avg Win/Loss, Largest Win/Loss
- Max Consecutive Wins/Losses
- Monte Carlo VaR, CVaR
- Walk-Forward Consistency Score

## Strategy Mutation

The genetic algorithm evolves strategies through:
- Parameter perturbation
- Indicator swap/add/remove
- Condition modification
- Risk parameter mutation
- Crossover between strategies

## License

MIT
