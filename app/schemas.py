"""数据模型定义（Pydantic）。

打分结果结构，前后端共用。Ollama 的结构化输出也按这个 JSON Schema 约束。
综合分（overall_score）不再由模型直接输出，而是由后端按用户设定的维度权重计算。
"""

from pydantic import BaseModel, Field
from typing import List, Dict


class DimensionScore(BaseModel):
    name: str = Field(..., description="维度名称")
    score: int = Field(..., ge=0, le=100, description="该维度得分 0-100")
    comment: str = Field(..., description="该维度简短评语")
    basis: str = Field(..., description="打分依据：引用简历/岗位 JD 中的具体证据")


class ScoreResult(BaseModel):
    filename: str = Field("", description="来源文件名")
    overall_score: int = Field(0, ge=0, le=100, description="综合分（按权重计算）")
    dimensions: List[DimensionScore] = Field(..., description="各维度打分（含打分依据）")
    strengths: List[str] = Field(..., description="候选人优势点")
    gaps: List[str] = Field(..., description="与岗位要求的差距/风险点")
    recommend_interview: bool = Field(..., description="是否建议进入面试")
    summary: str = Field(..., description="一句话总结")
    basis: str = Field("", description="整体打分依据（综合评判理由）")


# 期望的维度（顺序即展示顺序；权重可自由调整）
EXPECTED_DIMENSIONS = [
    "专业技能",
    "工作经验",
    "教育背景",
    "项目与成果",
    "综合素质",
    "当前居住地",
]

# 默认权重（百分比，合计 100）。用户可在界面自由修改。
DEFAULT_WEIGHTS: Dict[str, int] = {
    "专业技能": 20,
    "工作经验": 20,
    "教育背景": 15,
    "项目与成果": 20,
    "综合素质": 15,
    "当前居住地": 10,
}


def compute_overall(dimensions: List[DimensionScore], weights: Dict[str, int]) -> int:
    """按权重计算综合分：Σ(分×权重) / Σ权重，结果四舍五入为 0-100 整数。"""
    total_w = 0
    weighted = 0
    for d in dimensions:
        w = max(0, int(weights.get(d.name, 0)))
        weighted += d.score * w
        total_w += w
    if total_w == 0:
        # 权重全为 0 时退化为简单平均
        if not dimensions:
            return 0
        return round(sum(d.score for d in dimensions) / len(dimensions))
    return round(weighted / total_w)


# 传给 Ollama 的 JSON Schema（结构化输出约束）。
# 注意：此处不再要求模型输出 overall_score，综合分由后端按权重计算。
SCORE_SCHEMA = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "comment": {"type": "string"},
                    "basis": {"type": "string"},
                },
                "required": ["name", "score", "comment", "basis"],
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "recommend_interview": {"type": "boolean"},
        "summary": {"type": "string"},
        "basis": {"type": "string"},
    },
    "required": [
        "dimensions",
        "strengths",
        "gaps",
        "recommend_interview",
        "summary",
        "basis",
    ],
}
