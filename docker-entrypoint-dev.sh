#!/bin/bash
set -e

# Start Vite dev server in background
cd /app/frontend
npm run dev -- --host 0.0.0.0 &

# Start FastAPI with hot reload
cd /app
uvicorn wsb_tracker.api.main:app --host 0.0.0.0 --port 8000 --reload
