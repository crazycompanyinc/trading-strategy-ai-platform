#!/bin/bash
# Start Trading Strategy AI Platform API
cd /root/trading-strategy-ai-platform/backend
nohup python3 -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 > /tmp/trading-api.log 2>&1 &
echo "API started, PID: $!"
sleep 2
curl -s http://localhost:8000/health | head -1
