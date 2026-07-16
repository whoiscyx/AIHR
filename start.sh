#!/usr/bin/env bash
# 启动本地简历 OCR + AI 打分服务
# 前提：已安装依赖（见 README），且 Ollama 服务已运行（ollama serve）。

set -e

# 切换到脚本所在目录，确保无论从哪里调用都能找到 .venv 与 app 包
cd "$(dirname "$0")"

# 优先 Linux/macOS 的 bin/activate，其次 Windows(Git Bash) 的 Scripts/activate
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f ".venv/Scripts/activate" ]; then
    source .venv/Scripts/activate
else
    echo "[错误] 未检测到虚拟环境 .venv，请先按 README 执行："
    echo "       python -m venv .venv"
    echo "       source .venv/bin/activate   # Windows(Git Bash): source .venv/Scripts/activate"
    echo "       pip install -r requirements.txt"
    exit 1
fi

echo "正在启动服务，请稍候……（首次加载模型可能稍慢）"
echo "打开浏览器访问： http://localhost:8000"
exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
