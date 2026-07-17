"""测试提示词模块与院校识别。"""

import pytest
from app.prompts import detect_schools, format_school_ref, build_messages


def test_detect_schools():
    """测试院校名称识别。"""
    text = "毕业于清华大学，曾就读北京大学"
    result = detect_schools(text)
    assert len(result) == 2
    assert ("清华大学", 1) in result
    assert ("北京大学", 2) in result
    assert result[0][1] <= result[1][1]

    text = "毕业于某某学院"
    result = detect_schools(text)
    assert len(result) == 0

    text = "本科：浙江大学，硕士：上海交通大学"
    result = detect_schools(text)
    assert len(result) >= 2


def test_format_school_ref():
    """测试院校排名引用格式化。"""
    text = "毕业于清华大学"
    result = format_school_ref(text)
    assert "清华大学" in result
    assert "软科2025第1名" in result
    assert "第一梯队" in result

    text = "毕业于某某学院"
    result = format_school_ref(text)
    assert "未识别到" in result


def test_build_messages():
    """测试消息构建。"""
    resume_text = "张三，3年Java开发经验，毕业于浙江大学"
    job_description = "招聘Java开发工程师，要求3年经验"
    messages = build_messages(resume_text, job_description)

    assert isinstance(messages, list)
    assert len(messages) == 2

    system_msg = messages[0]
    assert system_msg["role"] == "system"
    assert "技术招聘官" in system_msg["content"]

    user_msg = messages[1]
    assert user_msg["role"] == "user"
    assert "岗位需求 JD" in user_msg["content"]
    assert "候选人简历内容" in user_msg["content"]


def test_build_messages_with_preferred_schools():
    """测试带认可院校名单的消息构建。"""
    resume_text = "毕业于清华大学"
    job_description = "招聘工程师"
    preferred_schools = "清华大学\n北京大学"
    messages = build_messages(resume_text, job_description, preferred_schools)

    user_msg = messages[1]
    assert "认可院校名单" in user_msg["content"]
    assert "清华大学" in user_msg["content"]