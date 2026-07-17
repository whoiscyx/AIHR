"""FastAPI 应用入口。

接口：
  GET  /api/models   列出本机 Ollama 模型
  POST /api/score    批量上传简历 + 岗位JD + 选模型 + 维度权重 → 结构化打分（按综合分降序）
  POST /api/score/sse    批量评分（SSE 版本，实时推送进度）
  POST /api/recompute_weights  权重调整后实时重算综合分（无需重新调用 AI）
  GET  /            首页（前端单页）

配置项见 app/config.py，支持通过环境变量覆盖。
"""

import os
import json
import asyncio
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse, Response, StreamingResponse

# 文件安全验证：魔术字节（文件头）检查
FILE_MAGIC_BYTES = {
    ".pdf": b"%PDF-",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".bmp": b"BM",
    ".webp": b"RIFF\x00\x00\x00\x00WEBP",
    ".tif": b"II\x2a\x00",
    ".tiff": b"II\x2a\x00",
    ".docx": b"PK\x03\x04",
}

# 允许的 MIME 类型
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/bmp",
    "image/webp",
    "image/tiff",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

from app.ocr import extract_text_from_bytes, ocr_backend_info
from app.scorer import score_resume, list_models, DEFAULT_MODEL, DEFAULT_WEIGHTS
from app.schemas import EXPECTED_DIMENSIONS, compute_overall_from_dict
from app.config import (
    ALLOWED_EXTS,
    MAX_FILE_BYTES,
    MAX_FILES,
    MAX_WORKERS,
)

def verify_file(data: bytes, filename: str) -> str | None:
    """验证文件安全性：检查扩展名、MIME 类型和魔术字节。

    返回错误信息（字符串），验证通过返回 None。
    """
    ext = Path(filename).suffix.lower()

    # 检查扩展名
    if ext not in ALLOWED_EXTS:
        return f"不支持的文件类型：{ext}"

    # 检查魔术字节（文件内容验证）
    magic = FILE_MAGIC_BYTES.get(ext)
    if magic and not data.startswith(magic):
        return f"文件内容与扩展名不匹配，请确认文件未损坏或类型正确。"

    return None


app = FastAPI(title="本地简历 OCR + AI 打分", version="2.0.0")

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = BASE_DIR / "static" / "index.html"


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


def _process_resume(
    filename: str,
    data: bytes,
    jd: str,
    model: str,
    weights_map: dict,
    preferred_schools: str,
) -> dict:
    """处理单份简历（同步函数，用于并行执行）。"""
    # 文件安全验证
    verify_err = verify_file(data, filename)
    if verify_err:
        return {"error": verify_err}

    if len(data) > MAX_FILE_BYTES:
        return {"error": "文件过大（上限 20MB）"}

    try:
        text = extract_text_from_bytes(data, filename)
    except (RuntimeError, ValueError) as e:
        return {"error": str(e)}

    if not text or not text.strip():
        return {"error": "无法从简历中提取到任何文本，请确认文件未损坏或尝试更清晰的扫描件。"}

    try:
        scored = score_resume(text, jd, model, weights_map, preferred_schools)
    except RuntimeError as e:
        return {"error": str(e)}

    scored["filename"] = filename
    return scored


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

    # 先读取所有文件数据（异步）并进行安全验证
    file_items = []
    errors = []
    for upload in files:
        filename = upload.filename or "resume.pdf"
        data = await upload.read()

        # 文件安全验证
        verify_err = verify_file(data, filename)
        if verify_err:
            errors.append({"filename": filename, "error": verify_err})
            continue

        if len(data) > MAX_FILE_BYTES:
            errors.append({"filename": filename, "error": "文件过大（上限 20MB）"})
            continue
        file_items.append((filename, data))

    # 并行处理简历（限制并发数，避免资源耗尽）
    max_workers = min(MAX_WORKERS, len(file_items))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        tasks = [
            asyncio.get_event_loop().run_in_executor(
                executor,
                _process_resume,
                filename,
                data,
                jd,
                model,
                weights_map,
                preferred_schools,
            )
            for filename, data in file_items
        ]
        results = await asyncio.gather(*tasks)

    # 分离成功和失败结果
    success_results = []
    for res in results:
        if "error" in res:
            errors.append({"filename": res.get("filename", "unknown"), "error": res["error"]})
        else:
            success_results.append(res)

    # 按综合分降序排序
    success_results.sort(key=lambda r: r.get("overall_score", 0), reverse=True)

    return {
        "count": len(success_results),
        "weights": weights_map,
        "results": success_results,
        "errors": errors,
    }


async def _process_resume_with_progress(
    index: int,
    total: int,
    filename: str,
    data: bytes,
    jd: str,
    model: str,
    weights_map: dict,
    preferred_schools: str,
    progress_queue: asyncio.Queue,
):
    """处理单份简历并推送进度（用于 SSE）。"""
    await progress_queue.put({
        "type": "processing",
        "index": index,
        "total": total,
        "filename": filename,
        "status": "开始处理",
    })

    try:
        text = extract_text_from_bytes(data, filename)
        if not text or not text.strip():
            await progress_queue.put({
                "type": "error",
                "index": index,
                "total": total,
                "filename": filename,
                "error": "无法从简历中提取到任何文本，请确认文件未损坏或尝试更清晰的扫描件。",
            })
            return

        await progress_queue.put({
            "type": "processing",
            "index": index,
            "total": total,
            "filename": filename,
            "status": "正在调用 AI 打分...",
        })

        scored = score_resume(text, jd, model, weights_map, preferred_schools)
        scored["filename"] = filename

        await progress_queue.put({
            "type": "completed",
            "index": index,
            "total": total,
            "filename": filename,
            "score": scored.get("overall_score", 0),
            "result": scored,
        })
        return scored

    except (RuntimeError, ValueError) as e:
        await progress_queue.put({
            "type": "error",
            "index": index,
            "total": total,
            "filename": filename,
            "error": str(e),
        })
        return


@app.post("/api/score/sse")
async def api_score_sse(
    resumes: list[UploadFile] = File(..., description="一个或多个简历文件（PDF/图片/DOCX）"),
    jd: str = Form(..., description="岗位需求描述"),
    model: str = Form(DEFAULT_MODEL, description="Ollama 模型名"),
    weights: str = Form("{}", description="维度权重 JSON，如 {\"专业技能\":20,...}"),
    preferred_schools: str = Form("", description="认可院校名单（可选，每行/逗号分隔一个校名）"),
):
    """批量评分（SSE 版本，实时推送进度）。

    通过 Server-Sent Events 实时推送处理进度，前端可显示当前处理进度。
    """
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

    # 先读取所有文件数据（异步）并进行安全验证
    file_items = []
    errors = []
    for upload in files:
        filename = upload.filename or "resume.pdf"
        data = await upload.read()

        # 文件安全验证
        verify_err = verify_file(data, filename)
        if verify_err:
            errors.append({"filename": filename, "error": verify_err})
            continue

        if len(data) > MAX_FILE_BYTES:
            errors.append({"filename": filename, "error": "文件过大（上限 20MB）"})
            continue
        file_items.append((filename, data))

    total = len(file_items)

    # SSE 生成器
    async def event_generator():
        progress_queue: asyncio.Queue = asyncio.Queue()
        success_results = []
        all_errors = list(errors)

        # 启动并行处理任务
        tasks = []
        for i, (filename, data) in enumerate(file_items):
            task = asyncio.create_task(
                _process_resume_with_progress(
                    i + 1,
                    total,
                    filename,
                    data,
                    jd,
                    model,
                    weights_map,
                    preferred_schools,
                    progress_queue,
                )
            )
            tasks.append(task)

        # 收集进度事件
        completed_count = 0
        while completed_count < total:
            event = await progress_queue.get()
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            if event["type"] == "completed":
                success_results.append(event["result"])
                completed_count += 1
            elif event["type"] == "error":
                all_errors.append({
                    "filename": event["filename"],
                    "error": event["error"],
                })
                completed_count += 1

        # 等待所有任务完成
        await asyncio.gather(*tasks)

        # 按综合分降序排序
        success_results.sort(key=lambda r: r.get("overall_score", 0), reverse=True)

        # 发送最终结果
        yield f"data: {json.dumps({
            'type': 'finish',
            'count': len(success_results),
            'weights': weights_map,
            'results': success_results,
            'errors': all_errors,
        }, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@app.post("/api/recompute_weights")
async def api_recompute_weights(
    results: list[dict] = Form(..., description="原始评分结果列表（含维度分）"),
    weights: str = Form("{}", description="新的维度权重 JSON"),
):
    """权重调整后实时重算综合分（无需重新调用 AI）。

    前端修改权重后调用此接口，后端按新权重重新计算综合分并排序，
    避免前端重复实现计算逻辑，保证前后端一致。
    """
    try:
        w = json.loads(weights) if weights else {}
    except json.JSONDecodeError:
        w = {}
    weights_map = {k: int(v) for k, v in w.items() if str(k) in EXPECTED_DIMENSIONS}
    for k in EXPECTED_DIMENSIONS:
        weights_map.setdefault(k, DEFAULT_WEIGHTS.get(k, 0))

    for res in results:
        dims = res.get("dimensions", [])
        res["overall_score"] = compute_overall_from_dict(dims, weights_map)
        res["recommend_interview"] = res["overall_score"] >= 70

    results.sort(key=lambda r: r.get("overall_score", 0), reverse=True)

    return {
        "count": len(results),
        "weights": weights_map,
        "results": results,
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
