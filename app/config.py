"""统一配置管理：集中管理所有可配置参数。

所有配置项均支持通过环境变量覆盖，便于部署和调试。
"""

import os
from typing import Set, Dict


# ── 服务器配置 ──────────────────────────────────────────────────────────────
HOST: str = os.environ.get("HOST", "127.0.0.1")
PORT: int = int(os.environ.get("PORT", "8000"))


# ── 文件上传配置 ────────────────────────────────────────────────────────────
ALLOWED_EXTS: Set[str] = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".docx"}
MAX_FILE_BYTES: int = int(os.environ.get("MAX_FILE_BYTES", str(20 * 1024 * 1024)))  # 单文件 20MB
MAX_FILES: int = int(os.environ.get("MAX_FILES", "50"))  # 批量上限


# ── OCR 引擎配置 ────────────────────────────────────────────────────────────
# 默认指向本机安装的 Umi-OCR Paddle 版自带的 PaddleOCR-json 引擎。
# 如需换版本/路径，设置环境变量 UMI_OCR_EXE 即可（指向 PaddleOCR-json.exe）。
DEFAULT_UMI_OCR_EXE: str = os.environ.get(
    "UMI_OCR_EXE",
    r"D:\software\OCR\Umi-OCR_Paddle_v2.1.5\UmiOCR-data\plugins\win7_x64_PaddleOCR-json\PaddleOCR-json.exe",
)

# 引擎进程初始化超时（秒）。Paddle 模型加载在机械盘/首启可能较慢。
ENGINE_INIT_TIMEOUT: int = int(os.environ.get("UMI_OCR_INIT_TIMEOUT", "90"))

# 文本型 PDF 抽取后，若去空白字符长度小于此值，判定为扫描件，改用 OCR
SCANNED_THRESHOLD: int = int(os.environ.get("SCANNED_THRESHOLD", "60"))


# ── AI 模型配置 ────────────────────────────────────────────────────────────
DEFAULT_MODEL: str = os.environ.get("DEFAULT_MODEL", "qwen3.5:4b")
MODEL_TEMPERATURE: float = float(os.environ.get("MODEL_TEMPERATURE", "0.2"))
MODEL_NUM_CTX: int = int(os.environ.get("MODEL_NUM_CTX", "32768"))


# ── 评分维度配置 ────────────────────────────────────────────────────────────
# 期望的维度（顺序即展示顺序；权重可自由调整）
EXPECTED_DIMENSIONS: list = [
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


# ── 并行处理配置 ────────────────────────────────────────────────────────────
# 最大并发数（限制线程池大小，避免资源耗尽）
MAX_WORKERS: int = int(os.environ.get("MAX_WORKERS", "4"))