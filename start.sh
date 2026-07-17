#!/usr/bin/env bash
# 启动本地简历 OCR + AI 打分服务（自动创建 venv 并安装依赖）
set -e

# 切换到脚本所在目录，确保无论从哪里调用都能找到 .venv 与 app 包
cd "$(dirname "$0")"

# 若虚拟环境不存在则创建
if [ ! -f ".venv/bin/activate" ] && [ ! -f ".venv/Scripts/activate" ]; then
    echo "[setup] 未检测到 .venv，正在创建虚拟环境 ..."
    python3 -m venv .venv || python -m venv .venv
fi

# 激活 venv（兼容 Linux/macOS 与 Windows Git Bash）
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    source .venv/Scripts/activate
fi

# 若依赖缺失则自动安装
if ! python -c "import fastapi" >/dev/null 2>&1; then
    echo "[setup] 正在安装依赖（requirements.txt）..."
    python -m pip install --upgrade pip
    pip install -r requirements.txt
fi

echo "正在启动服务，请稍候……（首次加载模型可能稍慢）"
echo "打开浏览器访问： http://127.0.0.1:8000"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
