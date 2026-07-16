#!/usr/bin/env bash
# 启动本地简历 OCR + AI 打分服务
# 前提：已安装依赖（见 README），且 Ollama 服务已运行（ollama serve）。
set -e
source .venv/Scripts/activate 2>/dev/null || source .venv/bin/activate 2>/dev/null
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
