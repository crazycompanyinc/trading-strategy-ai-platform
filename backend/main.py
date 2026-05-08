"""
Trading Strategy AI Platform v2 - Main Application
FastAPI backend + WebSocket. Single unified agent flow.
"""
import os, json, uuid, asyncio
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timezone

# Load .env
for p in [Path.home() / ".hermes" / ".env", Path(".env")]:
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and v and k not in os.environ:
                    os.environ[k] = v
        break

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn

from agent.trading_agent import TradingAgent
from strategy.parser import StrategyParser
from backtester.engine import BacktestEngine
from mutator.genetic import GeneticMutator
from mt5.generator import MT5Generator
from reports.generator import ReportGenerator

app = FastAPI(title="Trading Strategy AI Platform", version="2.3.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

agent = TradingAgent()
parser = StrategyParser()
backtester = BacktestEngine()
mutator = GeneticMutator()
mt5_gen = MT5Generator()
report_gen = ReportGenerator()
sessions: Dict[str, dict] = {}
active_ws: Dict[str, WebSocket] = {}


class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    images: Optional[List[str]] = None


@app.get("/")
async def root():
    return {"status": "ok", "app": "Trading Strategy AI Platform", "version": "2.3.0"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.post("/api/chat")
async def chat(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if sid not in sessions:
        sessions[sid] = {"id": sid, "created_at": datetime.now(timezone.utc).isoformat(), "history": [], "current_strategy": None}

    result = await agent.process_message(req.message, req.images or [], sid, sessions)

    sessions[sid]["history"].append({"role": "user", "content": req.message, "timestamp": datetime.now(timezone.utc).isoformat()})
    sessions[sid]["history"].append({"role": "assistant", "content": result.get("response", ""), "timestamp": datetime.now(timezone.utc).isoformat()})
    if result.get("strategy"):
        sessions[sid]["current_strategy"] = result["strategy"]

    return {"session_id": sid, **result}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    sid = req.session_id or str(uuid.uuid4())
    if sid not in sessions:
        sessions[sid] = {"id": sid, "created_at": datetime.now(timezone.utc).isoformat(), "history": [], "current_strategy": None}

    async def event_stream():
        yield f"data: {json.dumps({'type': 'start', 'session_id': sid})}\n\n"
        queue = asyncio.Queue()

        async def on_progress(state):
            await queue.put(state)

        # Run agent
        result = await agent.process_message(req.message, req.images or [], sid, sessions)

        sessions[sid]["history"].append({"role": "user", "content": req.message, "timestamp": datetime.now(timezone.utc).isoformat()})
        sessions[sid]["history"].append({"role": "assistant", "content": result.get("response", ""), "timestamp": datetime.now(timezone.utc).isoformat()})

        yield f"data: {json.dumps({'type': 'complete', 'session_id': sid, **result})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"})


@app.post("/api/backtest")
async def run_backtest(req: dict):
    try:
        result = backtester.run(strategy=req["strategy"], symbol=req.get("symbol", "EURUSD"),
                                timeframe=req.get("timeframe", "H1"))
        return {"status": "success", "results": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/mutate")
async def run_mutate(req: dict):
    try:
        results = mutator.evolve(base_strategy=req["strategy"], population_size=req.get("population_size", 15),
                                 generations=req.get("generations", 5))
        return {"status": "success", "mutations": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/export/mt5")
async def export_mt5(req: dict):
    try:
        code = mt5_gen.generate(req.get("strategy", req))
        return {"status": "success", "code": code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/robustness")
async def run_robustness(req: dict):
    try:
        results = backtester.run_robustness_tests(strategy=req["strategy"])
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/session/{sid}")
async def get_session(sid: str):
    if sid not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[sid]


@app.delete("/api/session/{sid}")
async def delete_session(sid: str):
    sessions.pop(sid, None)
    return {"status": "deleted"}


@app.websocket("/ws/{sid}")
async def ws_endpoint(ws: WebSocket, sid: str):
    await ws.accept()
    active_ws[sid] = ws
    if sid not in sessions:
        sessions[sid] = {"id": sid, "created_at": datetime.now(timezone.utc).isoformat(), "history": [], "current_strategy": None}
    try:
        while True:
            data = json.loads(await ws.receive_text())
            msg_type = data.get("type", "chat")
            if msg_type == "chat":
                result = await agent.process_message(data.get("content", ""), data.get("images", []), sid, sessions)
                await ws.send_json({"type": "response", **result})
            elif msg_type == "backtest":
                r = backtester.run(strategy=data["strategy"], symbol=data.get("symbol", "EURUSD"),
                                   timeframe=data.get("timeframe", "H1"))
                await ws.send_json({"type": "backtest_results", "results": r})
            elif msg_type == "mutate":
                r = mutator.evolve(base_strategy=data["strategy"], population_size=data.get("population_size", 15),
                                   generations=data.get("generations", 5))
                await ws.send_json({"type": "mutation_results", "mutations": r})
    except WebSocketDisconnect:
        active_ws.pop(sid, None)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, workers=1)
