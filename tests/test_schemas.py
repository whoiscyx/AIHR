"""测试数据模型与综合分计算。"""

import pytest
from app.schemas import (
    DimensionScore,
    ScoreResult,
    compute_overall,
    compute_overall_from_dict,
    EXPECTED_DIMENSIONS,
    DEFAULT_WEIGHTS,
)


def test_compute_overall():
    """测试综合分计算。"""
    dims = [
        DimensionScore(name="专业技能", score=80, comment="", basis=""),
        DimensionScore(name="工作经验", score=90, comment="", basis=""),
        DimensionScore(name="教育背景", score=70, comment="", basis=""),
        DimensionScore(name="项目与成果", score=85, comment="", basis=""),
        DimensionScore(name="综合素质", score=75, comment="", basis=""),
        DimensionScore(name="当前居住地", score=100, comment="", basis=""),
    ]

    result = compute_overall(dims, DEFAULT_WEIGHTS)
    assert isinstance(result, int)
    assert 0 <= result <= 100

    zero_weights = {k: 0 for k in EXPECTED_DIMENSIONS}
    avg_result = compute_overall(dims, zero_weights)
    expected_avg = round(sum(d.score for d in dims) / len(dims))
    assert avg_result == expected_avg


def test_compute_overall_from_dict():
    """测试从字典格式计算综合分。"""
    dims = [
        {"name": "专业技能", "score": 80},
        {"name": "工作经验", "score": 90},
        {"name": "教育背景", "score": 70},
        {"name": "项目与成果", "score": 85},
        {"name": "综合素质", "score": 75},
        {"name": "当前居住地", "score": 100},
    ]

    result = compute_overall_from_dict(dims, DEFAULT_WEIGHTS)
    assert isinstance(result, int)
    assert 0 <= result <= 100


def test_empty_dimensions():
    """测试空维度列表。"""
    result = compute_overall([], DEFAULT_WEIGHTS)
    assert result == 0

    result_dict = compute_overall_from_dict([], DEFAULT_WEIGHTS)
    assert result_dict == 0


def test_dimension_score_validation():
    """测试维度评分数据验证。"""
    dim = DimensionScore(name="专业技能", score=80, comment="良好", basis="有相关经验")
    assert dim.name == "专业技能"
    assert dim.score == 80

    with pytest.raises(Exception):
        DimensionScore(name="专业技能", score=101, comment="", basis="")

    with pytest.raises(Exception):
        DimensionScore(name="专业技能", score=-1, comment="", basis="")


def test_score_result_validation():
    """测试评分结果数据验证。"""
    dims = [DimensionScore(name="专业技能", score=80, comment="", basis="")]
    result = ScoreResult(
        filename="test.pdf",
        overall_score=80,
        dimensions=dims,
        strengths=["经验丰富"],
        gaps=[],
        recommend_interview=True,
        summary="推荐面试",
        basis="综合匹配度高",
    )
    assert result.filename == "test.pdf"
    assert result.overall_score == 80
    assert result.recommend_interview is True