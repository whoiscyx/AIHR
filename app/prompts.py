"""提示词模板：把简历文本 + 岗位 JD 组装成发给大模型的消息。"""

from typing import List, Tuple

from app.rank_data import RANK_LIST, RANK_DICT

# 软科 2025 中国大学排名（主榜 BCUR）Top500 已内置为离线查表（见 app/rank_data.py）。
# 评分时由 build_messages 自动从简历文本识别校名，并注入其精确软科名次，
# 避免每次请求都重复 500 条榜单、节省 token 且更精准。

# 第一梯队：软科2025前30（作为显性强调参考）
SHANGHAI_RANK_2025_TOP = [n for _, n in RANK_LIST[:30]]

# 完整 Top500 榜单文本（名次 校名，按名次升序；并列名次同等对待），供模型全局参照。
SHANGHAI_RANK_2025_FULL = "\n".join(f"{r}. {n}" for r, n in RANK_LIST)

# 院校分层说明（教育背景维度专用），与软科排名互为补充。
SCHOOL_TIER_HINT = (
    "院校层次参考（结合「软科2025中国大学排名 Top500」与以下规则）：\n"
    "  第一梯队：软科2025前30（见上清单，如清华/北大/浙大等）；\n"
    "  其余按名次段位：31-100 > 101-200 > 201-300 > 301-500 > 500以外；\n"
    "  一般 985/211/双一流 院校对应高名次段位，但请以【候选人院校的软科2025名次】为准；\n"
    "  海外院校：参考 QS / 泰晤士等国际排名与综合声誉判断层次。\n"
    "层次越高，教育背景分越应占优；同等条件下院校层次高者适当加分。"
    "若下方【候选人院校的软科2025名次】已给出精确名次，请优先依据它评判，并在 basis 中引用校名与名次。"
)


def detect_schools(text: str) -> List[Tuple[str, int]]:
    """从简历文本中识别软科2025 Top500 院校名称，返回按名次升序的 [(name, rank)]。"""
    found: List[Tuple[str, int]] = []
    for name, rank in RANK_DICT.items():
        if name in text:
            found.append((name, rank))
    found.sort(key=lambda x: x[1])
    return found


def format_school_ref(text: str) -> str:
    """生成候选人院校的软科2025精确名次段落（评分核心依据）。"""
    schools: List[Tuple[str, int]] = detect_schools(text)
    if not schools:
        return "（简历中未识别到软科2025 Top500 院校名称；请依据学历层次、专业契合及可能的院校标签综合判断）"
    parts: List[str] = []
    for name, rank in schools:
        if rank <= 30:
            tier = "第一梯队"
        elif rank <= 100:
            tier = "前100"
        elif rank <= 200:
            tier = "前200"
        elif rank <= 300:
            tier = "前300"
        elif rank <= 500:
            tier = "前500"
        else:
            tier = "500以外"
        parts.append(f"{name}（软科2025第{rank}名，{tier}）")
    return "；".join(parts)


SYSTEM_PROMPT = """你是一位资深的技术招聘官与简历评估专家，擅长结合「岗位需求」对候选人简历做客观、可量化、有依据的匹配度评估。

评估要求：
1. 以岗位 JD 为锚点，判断候选人在该岗位上的匹配程度，不要泛泛而谈。
2. dimensions 必须且只能包含以下 6 个维度，每个维度给出：
   - score：0-100 的整数分；
   - comment：一句话中文评语；
   - basis：打分依据——必须引用简历原文或岗位 JD 中的具体信息（如技能关键词、年限、学历、毕业院校、项目数据、现居城市等）来说明为什么给这个分。
   维度清单：
   - 专业技能（岗位要求的硬技能/工具/语言掌握度）
   - 工作经验（相关行业/岗位年限与深度）
   - 教育背景（学历层次、专业与岗位的契合，以及【毕业院校在「软科2025中国大学排名」中的名次/层次】；须优先参考下方【候选人院校的软科2025名次】给出的精确名次，并在 basis 中说明院校层次/排名对分数的影响，引用简历中的校名与名次）
   - 项目与成果（项目经历、量化成果、解决问题的能力）
   - 综合素质（沟通、自驱、领导力、稳定性等软素质）
   - 当前居住地（候选人现居地与该岗位工作地/可接受地的匹配度；若 JD 未说明地点，则按“是否便于到岗、稳定性”酌情给分，并在 basis 中说明依据）
3. strengths 列出 2-5 条候选人相对岗位的优势。
4. gaps 列出 1-4 条与岗位要求的差距或风险点（可空数组）。
5. recommend_interview 为布尔值：核心维度无致命硬伤且综合匹配较好时建议面试。
6. summary 用一句话概括是否推荐及核心理由。
7. basis（整体）用 2-4 句话综合说明本次评分的总体依据与关键判断。

综合分由系统按各维度权重自动计算，你无需输出 overall_score。
只输出符合给定 JSON Schema 的内容，不要输出任何额外说明文字。"""

USER_TEMPLATE = """【岗位需求 JD】
{job_description}

【候选人简历内容】
{resume_text}

【候选人院校的软科2025名次（由内置软科2025 Top500 榜单自动识别，作为「教育背景」维度优先评判依据）】
{school_rank_ref}

【院校分层参考（软科2025中国大学排名 主榜 Top500；数据来源：shanghairanking.cn）】
第一梯队（前30）：{shanghai_top}
完整 Top500 榜单（名次越靠前层次越高；并列名次同等对待）：
{full_rank}
{school_tier_hint}

【认可院校名单（招聘方自定义；名单内院校在「教育背景」维度视为强匹配，若为空则忽略此约束）】
{preferred_schools}"""


def build_messages(
    resume_text: str,
    job_description: str,
    preferred_schools: str = "",
) -> List[dict]:
    # 控制长度，避免超出上下文（简历一般不会这么长，但做个保险）
    resume_text = resume_text.strip()[:16000]
    job_description = job_description.strip()[:4000]
    preferred_schools = (preferred_schools or "").strip()

    # 自动识别简历院校在软科2025中的精确名次（评分核心依据）
    school_rank_ref = format_school_ref(resume_text)

    user_content = USER_TEMPLATE.format(
        job_description=job_description,
        resume_text=resume_text,
        school_rank_ref=school_rank_ref,
        shanghai_top="、".join(SHANGHAI_RANK_2025_TOP),
        full_rank=SHANGHAI_RANK_2025_FULL,
        school_tier_hint=SCHOOL_TIER_HINT,
        preferred_schools=preferred_schools or "（未提供）",
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
