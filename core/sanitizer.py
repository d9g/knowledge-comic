"""
知识漫画生成器 — 输入安全过滤

NOTE: 所有用户输入必须经过此模块过滤后才能写入 JSON 数据。
防止 XSS 注入、SQL 注入、控制字符等安全问题。
"""
import html
import logging
import re

logger = logging.getLogger(__name__)

# NOTE: 危险 SQL 关键字模式（全词匹配，防止误伤正常中文）
_SQL_PATTERNS = re.compile(
    r"\b(DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|UPDATE\s+.*SET|"
    r"UNION\s+SELECT|OR\s+1\s*=\s*1|AND\s+1\s*=\s*1|"
    r"--\s|;\s*DROP|;\s*DELETE|'\s*OR\s*')\b",
    re.IGNORECASE,
)

# NOTE: 控制字符（保留换行和空格）
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# NOTE: HTML 标签
_HTML_TAGS = re.compile(r"<[^>]+>")

# 字段长度限制
FIELD_LIMITS = {
    "title": 30,
    "heading": 20,
    "text": 200,
    "footer": 50,
    "icons": 10,
}


def sanitize_text(text: str, field_type: str = "text") -> str:
    """
    过滤用户输入的文本

    @param text: 原始输入
    @param field_type: 字段类型（title/heading/text/footer/icons）
    @returns: 安全的文本
    """
    if not text:
        return ""

    # 1. 去除控制字符
    text = _CONTROL_CHARS.sub("", text)

    # 2. 去除 HTML 标签（防 XSS）
    text = _HTML_TAGS.sub("", text)

    # 3. 转义 HTML 实体
    text = html.unescape(text)

    # 4. 检测 SQL 注入模式
    if _SQL_PATTERNS.search(text):
        logger.warning("[安全] 检测到疑似 SQL 注入: %s", text[:100])
        text = _SQL_PATTERNS.sub("", text)

    # 5. 去除首尾空白
    text = text.strip()

    # 6. 长度限制
    max_len = FIELD_LIMITS.get(field_type, 200)
    if len(text) > max_len:
        text = text[:max_len]

    return text


def sanitize_comic_data(data: dict) -> dict:
    """
    过滤整个漫画数据字典

    @param data: AI 生成的原始 JSON 数据
    @returns: 安全过滤后的数据
    """
    data["title"] = sanitize_text(data.get("title", ""), "title")
    from config import get_random_footer
    data["footer"] = sanitize_text(data.get("footer") or get_random_footer(), "footer")

    # 过滤 panels 列表
    for panel in data.get("panels", []):
        panel["heading"] = sanitize_text(panel.get("heading", ""), "heading")
        panel["text"] = sanitize_text(panel.get("text", ""), "text")
        # icons 只保留 emoji 和短文本
        if "icons" in panel:
            panel["icons"] = [
                sanitize_text(icon, "icons") for icon in panel["icons"]
            ]

    # 过滤其他列表字段（medical_guide/recipe_card 模板）
    for list_key in ["sections", "ingredients", "prep_steps", "cooking_steps"]:
        for item in data.get(list_key, []):
            for text_key in ["heading", "text", "name", "description", "step"]:
                if text_key in item:
                    item[text_key] = sanitize_text(item[text_key], "text")

    return data
