#!/usr/bin/env bash
# Backend (FastAPI/uvicorn) - repo root'tan çağrılır
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../webapp/backend"
if [ -f ".venv/bin/python" ]; then
    .venv/bin/python -m uvicorn app.main:app --reload --port 8000
else
    python -m uvicorn app.main:app --reload --port 8000
fi
