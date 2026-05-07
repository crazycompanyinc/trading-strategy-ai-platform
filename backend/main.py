"""
Trading Strategy AI Platform - Main Application
FastAPI backend with WebSocket support for real-time chat
"""
import os
import uuid
import json
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
import uvicorn

from agent.trading_agent import TradingAgent
from strategy.parser import StrategyParser
from strategy.models import StrategyIR
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator

# ─── App setup ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Trading Strategy AI Platform",
    description="AI-powered trading strategy research via natural language",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Global state ──────────────────────────────────────────────────────────────

agent = TradingAgent()
parser = StrategyParser()
backtester = BacktestEngine()
mutator = GeneticMutator()
mt5_gen = MT5Generator()
report_gen = ReportGenerator()

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Session storage
sessions: Dict[str, dict] = {}

# ─── Models ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    images: Optional[List[str]] = None  # base64-encoded images

class ChatResponse(BaseModel):
    session_id: str
    response: str
    strategy: Optional[dict] = None
    backtest_results: Optional[dict] = None
    mt5_code: Optional[str] = None

class BacktestRequest(BaseModel):
    strategy: dict
    symbol: str = "EURUSD"
    timeframe: str = "H1"
    start_date: str = "2022-01-01"
    end_date: str = "2024-01-01"
    initial_capital: float = 10000.0
    commission: float = 0.001

class MutationRequest(BaseModel):
    strategy: dict
    population_size: int = 20
    generations: int = 10
    objectives: List[str] = Field(default=["sharpe", "profit_factor", "total_return"])
    constraints: Optional[dict] = None

class RobustnessRequest(BaseModel):
    strategy: dict
    n_monte_carlo: int = 1000
    n_walk_forward: int = 5
    confidence_level: float = 0.95

# ─── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "app": "Trading Strategy AI Platform", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Process a natural language trading idea."""
    sid = request.session_id or str(uuid.uuid4())

    if sid not in sessions:
        sessions[sid] = {
            "id": sid,
            "created_at": datetime.utcnow().isoformat(),
            "history": [],
            "current_strategy": None
        }

    # Process via agent
    result = await agent.process_message(
        message=request.message,
        images=request.images or [],
        session=sid,
        sessions=sessions
    )

    sessions[sid]["history"].append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    sessions[sid]["history"].append({
        "role": "assistant",
        "content": result.get("response", ""),
        "timestamp": datetime.utcnow().isoformat()
    })

    if result.get("strategy"):
        sessions[sid]["current_strategy"] = result["strategy"]

    return ChatResponse(
        session_id=sid,
        response=result.get("response", ""),
        strategy=result.get("strategy"),
        backtest_results=result.get("backtest_results"),
        mt5_code=result.get("mt5_code")
    )

@app.post("/api/backtest")
async def run_backtest(request: BacktestRequest, background_tasks: BackgroundTasks):
    """Execute a backtest for a given strategy."""
    try:
        result = backtester.run(
            strategy=request.strategy,
            symbol=request.symbol,
            timeframe=request.timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            commission=request.commission
        )
        return {"status": "success", "results": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/mutate")
async def mutate_strategy(request: MutationRequest):
    """Run genetic mutation to evolve strategy variants."""
    try:
        results = mutator.evolve(
            base_strategy=request.strategy,
            population_size=request.population_size,
            generations=request.generations,
            objectives=request.objectives,
            constraints=request.constraints or {}
        )
        return {"status": "success", "mutations": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/robustness")
async def run_robustness(request: RobustnessRequest):
    """Run robustness tests (Monte Carlo, walk-forward, etc.)."""
    try:
        backtester_inst = BacktestEngine()
        results = backtester_inst.run_robustness_tests(
            strategy=request.strategy,
            n_monte_carlo=request.n_monte_carlo,
            n_walk_forward=request.n_walk_forward,
            confidence_level=request.confidence_level
        )
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/export/mt5")
async def export_mt5(strategy: dict):
    """Generate MQL5 code from strategy."""
    try:
        code = mt5_gen.generate(strategy)
        return {"status": "success", "code": code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/report")
async def generate_report(backtest_results: dict):
    """Generate PDF report from backtest results."""
    try:
        report_path = report_gen.generate(backtest_results)
        return {"status": "success", "report_path": report_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """Upload an image for analysis."""
    try:
        contents = await file.read()
        # Save temporarily
        img_id = str(uuid.uuid4())
        img_path = f"/tmp/trading_imgs/{img_id}_{file.filename}"
        os.makedirs("/tmp/trading_imgs", exist_ok=True)
        with open(img_path, "wb") as f:
            f.write(contents)
        return {"status": "success", "image_id": img_id, "path": img_path}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session history and current state."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]

@app.delete("/api/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "deleted"}

# ─── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    active_connections[session_id] = websocket

    if session_id not in sessions:
        sessions[session_id] = {
            "id": session_id,
            "created_at": datetime.utcnow().isoformat(),
            "history": [],
            "current_strategy": None
        }

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type", "chat")

            if msg_type == "chat":
                result = await agent.process_message(
                    message=message.get("content", ""),
                    images=message.get("images", []),
                    session=session_id,
                    sessions=sessions
                )
                await websocket.send_json({
                    "type": "response",
                    "response": result.get("response", ""),
                    "strategy": result.get("strategy"),
                    "backtest_results": result.get("backtest_results"),
                    "mt5_code": result.get("mt5_code"),
                    "done": True
                })

            elif msg_type == "backtest":
                bt_result = backtester.run(
                    strategy=message["strategy"],
                    symbol=message.get("symbol", "EURUSD"),
                    timeframe=message.get("timeframe", "H1"),
                    start_date=message.get("start_date", "2022-01-01"),
                    end_date=message.get("end_date", "2024-01-01"),
                    initial_capital=message.get("initial_capital", 10000),
                    commission=message.get("commission", 0.001)
                )
                await websocket.send_json({
                    "type": "backtest_results",
                    "results": bt_result
                })

            elif msg_type == "mutate":
                mut_results = mutator.evolve(
                    base_strategy=message["strategy"],
                    population_size=message.get("population_size", 20),
                    generations=message.get("generations", 10),
                    objectives=message.get("objectives", ["sharpe", "profit_factor"]),
                    constraints=message.get("constraints", {})
                )
                await websocket.send_json({
                    "type": "mutation_results",
                    "mutations": mut_results
                })

    except WebSocketDisconnect:
        if session_id in active_connections:
            del active_connections[session_id]

# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
