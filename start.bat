@echo off
REM 启动本地简历 OCR + AI 打分服务
REM 前提：已安装依赖（见 README），且 Ollama 服务已运行（Windows 下打开 Ollama 应用即自动启动）。

call .venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
