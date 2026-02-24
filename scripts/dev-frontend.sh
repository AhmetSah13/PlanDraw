#!/usr/bin/env bash
# Frontend (Vite) - repo root'tan çağrılır
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../webapp/frontend"
npm run dev
