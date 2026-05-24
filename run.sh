#!/bin/bash
cd "$(dirname "$0")"
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8765 --reload --reload-exclude '.venv'
