"""FastAPI 应用入口。

接口：
  GET  /api/models   列出本机 Ollama 模型
  POST /api/score    批量上传简历 + 岗位JD + 选模型 + 维度权重 → 结构化打分（按综合分降序）
  GET  /            首页（前端单页）
"""

import os
import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response

from app.ocr import extract_text, ocr_backend_info
from app.scorer import score_resume, list_models, DEFAULT_MODEL, DEFAULT_WEIGHTS
from app.schemas import EXPECTED_DIMENSIONS

app = FastAPI(title="本地简历 OCR + AI 打分", version="2.0.0")

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = BASE_DIR / "static" / "index.html"

# 允许上传的类型
ALLOWED_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".docx"}
MAX_FILE_BYTES = 20 * 1024 * 1024  # 单文件 20MB
MAX_FILES = 50  # 批量上限


@app.get("/api/models")
def api_models():
    models = list_models()
    return {"models": models, "default": DEFAULT_MODEL}


@app.get("/api/weights")
def api_weights():
    """返回默认维度权重与维度顺序，供前端初始化权重编辑器。"""
    return {"dimensions": EXPECTED_DIMENSIONS, "weights": DEFAULT_WEIGHTS}


@app.get("/api/engine")
def api_engine():
    """返回当前使用的 OCR 后端信息（Umi-OCR / EasyOCR 兜底）。"""
    return ocr_backend_info()


@app.post("/api/score")
async def api_score(
    resumes: list[UploadFile] = File(..., description="一个或多个简历文件（PDF/图片/DOCX）"),
    jd: str = Form(..., description="岗位需求描述"),
    model: str = Form(DEFAULT_MODEL, description="Ollama 模型名"),
    weights: str = Form("{}", description="维度权重 JSON，如 {\"专业技能\":20,...}"),
    preferred_schools: str = Form("", description="认可院校名单（可选，每行/逗号分隔一个校名）"),
):
    if not resumes:
        raise HTTPException(status_code=422, detail="未收到任何简历文件")

    files = resumes if isinstance(resumes, list) else [resumes]
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=413, detail=f"一次最多上传 {MAX_FILES} 份简历")

    # 解析权重（非法/缺失则用默认）
    try:
        w = json.loads(weights) if weights else {}
    except json.JSONDecodeError:
        w = {}
    weights_map = {k: int(v) for k, v in w.items() if str(k) in EXPECTED_DIMENSIONS}
    for k in EXPECTED_DIMENSIONS:
        weights_map.setdefault(k, DEFAULT_WEIGHTS.get(k, 0))

    results = []
    errors = []

    for upload in files:
        filename = upload.filename or "resume.pdf"
        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTS:
            errors.append({"filename": filename, "error": f"不支持的文件类型：{ext}"})
            continue

        data = await upload.read()
        if len(data) > MAX_FILE_BYTES:
            errors.append({"filename": filename, "error": "文件过大（上限 20MB）"})
            continue

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as f:
                f.write(data)
                tmp_path = f.name

            try:
                text = extract_text(tmp_path, filename)
            except RuntimeError as e:
                errors.append({"filename": filename, "error": str(e)})
                continue

            if not text or not text.strip():
                errors.append({"filename": filename, "error": "无法从简历中提取到任何文本，请确认文件未损坏或尝试更清晰的扫描件。"})
                continue

            try:
                scored = score_resume(text, jd, model, weights_map, preferred_schools)
            except RuntimeError as e:
                errors.append({"filename": filename, "error": str(e)})
                continue

            scored["filename"] = filename
            results.append(scored)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.unlink(tmp_path)

    # 按综合分降序排序
    results.sort(key=lambda r: r.get("overall_score", 0), reverse=True)

    return {
        "count": len(results),
        "weights": weights_map,
        "results": results,
        "errors": errors,
    }


@app.get("/favicon.ico")
def favicon():
    """返回 204 空响应，避免浏览器自动请求 favicon 时刷出 404 日志。"""
    return Response(status_code=204)


@app.get("/")
def index():
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    return HTTPException(status_code=404, detail="前端页面未找到")
