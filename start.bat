@echo off
REM 启动本地简历 OCR + AI 打分服务
REM 前提：已安装依赖（见 README），且 Ollama 服务已运行（Windows 下打开 Ollama 应用即自动启动）。

SETLOCAL
REM 切换到脚本所在目录，确保无论从哪里调用都能找到 .venv 与 app 包
CD /D "%~dp0"

IF NOT EXIST ".venv\Scripts\activate.bat" (
    echo [错误] 未检测到虚拟环境 .venv，请先按 README 执行：
    echo        python -m venv .venv
    echo        .venv\Scripts\activate
    echo        pip install -r requirements.txt
    pause
    EXIT /B 1
)

call .venv\Scripts\activate.bat
echo 正在启动服务，请稍候……（首次加载模型可能稍慢）
echo 打开浏览器访问： http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
