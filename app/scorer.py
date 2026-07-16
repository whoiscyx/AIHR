"""打分模块：调用本地 Ollama 模型，对简历做结构化评分。

综合分（overall_score）由后端按用户设定的维度权重计算，模型只负责输出
各维度分数与打分依据（basis）。
"""

import json
import re
from typing import Optional

import ollama

from app.schemas import (
    SCORE_SCHEMA,
    EXPECTED_DIMENSIONS,
    DEFAULT_WEIGHTS,
    compute_overall,
)
from app.prompts import build_messages

DEFAULT_MODEL = "qwen3.5:4b"
GEN_OPTIONS = {"temperature": 0.2, "num_ctx": 32768}


def list_models() -> list:
    """列出本机 Ollama 已安装的模型名称。"""
    try:
        res = ollama.list()
        models = res.get("models") or []
        return [m.get("name") or m.get("model") for m in models if (m.get("name") or m.get("model"))]
    except Exception:
        # 服务未启动等情况，返回空，前端会提示
        return []


def _normalize(data: dict, weights: dict) -> dict:
    """校验并兜底补全维度，按权重计算综合分。"""
    # 维度兜底：若缺维度，补 0 分占位
    dims = data.get("dimensions") or []
    have = {d.get("name") for d in dims}
    for name in EXPECTED_DIMENSIONS:
        if name not in have:
            dims.append(
                {"name": name, "score": 0, "comment": "未识别到相关信息", "basis": "简历中未提供可评估该维度的信息。"}
            )
    # 保持期望顺序
    dims.sort(key=lambda d: EXPECTED_DIMENSIONS.index(d["name"]) if d["name"] in EXPECTED_DIMENSIONS else 99)

    # 数值夹紧
    for d in dims:
        try:
            d["score"] = max(0, min(100, int(d["score"])))
        except (TypeError, ValueError):
            d["score"] = 0
        d.setdefault("comment", "")
        d.setdefault("basis", "")

    data["dimensions"] = dims
    data["overall_score"] = compute_overall(
        [type("D", (), {"name": d["name"], "score": d["score"]})() for d in dims], weights
    )
    data.setdefault("strengths", [])
    data.setdefault("gaps", [])
    data.setdefault("recommend_interview", data["overall_score"] >= 70)
    data.setdefault("summary", "")
    data.setdefault("basis", "")
    return data


def _extract_json_from_text(text: str) -> Optional[dict]:
    """结构化输出失败时的兜底：从自由文本里抠出第一个 JSON 对象。"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def score_resume(
    resume_text: str,
    job_description: str,
    model: str = DEFAULT_MODEL,
    weights: Optional[dict] = None,
    preferred_schools: str = "",
) -> dict:
    """对简历打分，返回标准化 dict（含按权重计算的综合分）。

    preferred_schools: 招聘方自定义的认可院校名单（多行/逗号分隔的文本），
    作为「教育背景」维度的强匹配依据传入提示词。
    """
    weights = weights or DEFAULT_WEIGHTS
    messages = build_messages(resume_text, job_description, preferred_schools=preferred_schools)

    # 优先用结构化输出（Ollama format 约束）
    try:
        resp = ollama.chat(
            model=model,
            messages=messages,
            format=SCORE_SCHEMA,
            options=GEN_OPTIONS,
        )
        content = resp["message"]["content"]
        data = json.loads(content)
    except Exception:
        # 兜底：不带 schema 再问一次，手动解析
        resp = ollama.chat(model=model, messages=messages, options=GEN_OPTIONS)
        data = _extract_json_from_text(resp["message"]["content"])
        if data is None:
            raise RuntimeError("模型未返回可解析的评分结果，请重试或更换模型。")

    return _normalize(data, weights)
