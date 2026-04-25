"""
知识漫画生成器 — 全局配置
"""
import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# ── 项目路径 ──
BASE_DIR = Path(__file__).parent
COMIC_TEMPLATES_DIR = BASE_DIR / "comic_templates"
FONTS_DIR = COMIC_TEMPLATES_DIR / "fonts"
LLM_TEMPLATES_DIR = BASE_DIR / "templates"
OUTPUT_DIR = BASE_DIR / "output"

# NOTE: 自定义模板清单文件路径
CUSTOM_TEMPLATES_MANIFEST = COMIC_TEMPLATES_DIR / "custom_templates.json"

# ── LLM 配置 ──
LLM_PROVIDERS = {
    "bailian": {
        "name": "百炼 (DashScope)",
        "base_url": "https://coding.dashscope.aliyuncs.com/v1",
        "models": [
            "qwen-plus",
            "qwen3.6-plus",
            "glm-5",
            "MiniMax-M2.5",
        ],
        "default_model": "qwen-plus",
        "env_key": "DASHSCOPE_API_KEY",
    },
    "deepseek": {
        "name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "default_model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "models": [
            "gpt-4o",
            "gpt-4o-mini",
        ],
        "default_model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
    "custom": {
        "name": "自定义 (兼容 OpenAI 协议)",
        "base_url": "",
        "models": [],
        "default_model": "",
        "env_key": "",
    },
}

# NOTE: 默认提供商
DEFAULT_PROVIDER = "bailian"

# ── 公众号引流 ──
# NOTE: 每次生成随机选一个公众号名称作为 footer，实现均匀引流
WECHAT_ACCOUNTS = [
    "琴墨书香的奇遇",
    "老杨讲理",
    "半盏茶说书",
    "居家能手小羊",
]


def get_random_footer() -> str:
    """
    随机生成一条公众号引流 footer

    NOTE: 使用 os.urandom 保证真随机，不依赖伪随机种子
    """
    import struct
    # NOTE: 用系统熵源生成真随机索引，避免 random 模块的伪随机周期性
    random_bytes = os.urandom(4)
    idx = struct.unpack("I", random_bytes)[0] % len(WECHAT_ACCOUNTS)
    return f"关注公众号「{WECHAT_ACCOUNTS[idx]}」免费生成"


# ── 访问控制 ──
# NOTE: Admin 后台密码保护（环境变量配置，为空则不需要密码）
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# NOTE: 微信关注限制开关
# 设为 true 时，用户需通过微信关注验证后才能使用生成功能
# 具体验证逻辑后续扩展，当前仅做开关控制
REQUIRE_WECHAT_FOLLOW = os.environ.get("REQUIRE_WECHAT_FOLLOW", "false").lower() == "true"

# 关注引导文案（开关开启时显示）
WECHAT_FOLLOW_GUIDE = os.environ.get(
    "WECHAT_FOLLOW_GUIDE",
    '请关注公众号，发送"激活"获取使用码',
)


# ── ComfyUI 配置 ──
# NOTE: 云端部署时通过环境变量 COMFYUI_URL 指向 frp 隧道映射的地址
# 本地开发时默认连接 localhost:8188
COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")

# ── 插画尺寸 ──
# NOTE: 512 是 SDXL 原生训练尺寸，清晰度最好
ILLUST_SIZE = {"width": 512, "height": 512}

# ── 内置模板配置 ──
TEMPLATE_PRESETS = {
    "cute_panels": {
        "name": "🎀 可爱四宫格",
        "description": "适合生活技巧、养生习惯、日常建议",
        "panel_count": 4,
        "keywords": ["习惯", "技巧", "建议", "方法", "方式", "注意", "好处"],
        "builtin": True,
    },
    "medical_guide": {
        "name": "🏥 图解教程",
        "description": "适合动作指导、穴位按摩、健身教程",
        "panel_count": 3,
        "keywords": ["动作", "穴位", "拉伸", "按摩", "姿势", "步骤", "教程"],
        "builtin": True,
    },
    "recipe_card": {
        "name": "🍲 食谱卡片",
        "description": "适合食谱、药膳、饮品制作",
        "panel_count": 6,
        "keywords": ["食材", "做法", "食谱", "煮", "炒", "汤", "粥", "茶"],
        "builtin": True,
    },
}


def _load_custom_templates_manifest() -> dict:
    """
    加载自定义模板清单

    NOTE: 清单保存在 comic_templates/custom_templates.json
    """
    if CUSTOM_TEMPLATES_MANIFEST.exists():
        try:
            return json.loads(CUSTOM_TEMPLATES_MANIFEST.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _scan_unregistered_templates(known_ids: set) -> dict:
    """
    扫描 comic_templates/ 目录中未注册的 HTML 模板

    NOTE: 处理用户手动放入的模板文件，自动添加到选择列表
    跳过以下划线开头的临时文件（如 _render_tmp.html, _preview_custom.html）
    """
    discovered = {}
    if not COMIC_TEMPLATES_DIR.exists():
        return discovered

    for html_file in COMIC_TEMPLATES_DIR.glob("*.html"):
        tpl_id = html_file.stem
        # 跳过已注册的和临时文件
        if tpl_id in known_ids or tpl_id.startswith("_"):
            continue
        discovered[tpl_id] = {
            "name": f"📄 {tpl_id}",
            "description": f"自动发现的模板（{html_file.name}）",
            "builtin": False,
        }
    return discovered


def get_all_templates() -> dict:
    """
    获取所有可用模板（内置 + 自定义清单 + 磁盘扫描）

    NOTE: 这是模板选择器应该调用的唯一入口，
    确保新保存的模板在重启后也能出现在列表中。

    @returns: 合并后的模板字典 {template_id: {name, description, ...}}
    """
    all_templates = dict(TEMPLATE_PRESETS)

    # 加载自定义模板清单
    custom = _load_custom_templates_manifest()
    for tpl_id, tpl_info in custom.items():
        if tpl_id not in all_templates:
            tpl_info["builtin"] = False
            all_templates[tpl_id] = tpl_info

    # 扫描磁盘上未注册的模板
    known_ids = set(all_templates.keys())
    discovered = _scan_unregistered_templates(known_ids)
    all_templates.update(discovered)

    return all_templates


def save_custom_template_meta(template_id: str, display_name: str, description: str = "") -> None:
    """
    将自定义模板元数据保存到清单文件

    NOTE: 在 admin 保存模板时调用，确保重启后模板仍在列表中

    @param template_id: 模板 ID（英文，与 HTML 文件名一致）
    @param display_name: 显示名称（中文）
    @param description: 描述
    """
    manifest = _load_custom_templates_manifest()
    manifest[template_id] = {
        "name": display_name or f"📄 {template_id}",
        "description": description or "用户自定义模板",
    }
    try:
        CUSTOM_TEMPLATES_MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info("[配置] 模板元数据已保存: %s", template_id)
    except Exception as e:
        logger.warning("[配置] 保存模板元数据失败: %s", e)


# ── 画风预设（复用 novel2video 的 ComfyUI 工作流思路）──
STYLE_PRESETS = {
    "kawaii": {
        "name": "🎀 可爱卡通",
        "suffix": (
            "kawaii illustration, cute chibi style, soft pastel colors, "
            "simple clean background, round shapes, adorable expression, "
            "children book illustration, flat color shading"
        ),
        # NOTE: 使用 SDXL Lightning 快速出图，插画不需要太精细
        "checkpoint": "dreamshaperXL_lightningDPMSDE.safetensors",
        "steps": 8,
        "cfg": 2.5,
    },
    "flat": {
        "name": "📐 扁平插画",
        "suffix": (
            "flat vector illustration, clean minimal design, "
            "solid color blocks, simple geometric shapes, "
            "modern infographic style, no outline, matte colors"
        ),
        "checkpoint": "dreamshaperXL_lightningDPMSDE.safetensors",
        "steps": 8,
        "cfg": 2.5,
    },
    "manhwa": {
        "name": "📱 韩漫风",
        "suffix": (
            "manhwa illustration, clean digital lineart, soft cel shading, "
            "pastel and muted color palette, Korean webtoon style, "
            "detailed eyes and expressive faces, smooth color gradients"
        ),
        "checkpoint": "dreamshaperXL_lightningDPMSDE.safetensors",
        "steps": 8,
        "cfg": 2.5,
    },
}

# ── 食物插画专用风格（强调清晰可辨认，允许卡通但不允许模糊艺术化）──
FOOD_PHOTO_STYLE = {
    "suffix": (
        "single subject centered on pure white background, "
        "clear sharp outline, flat lighting, no shadows, "
        "high contrast, product catalog style, isolated object"
    ),
    "negative": (
        "blurry, out of focus, bokeh, lens flare, light leak, "
        "motion blur, depth of field, haze, fog, glow, bloom, "
        "film grain, vignette, chromatic aberration, text, words, "
        "abstract, surreal, distorted, low quality, watermark, "
        "multiple objects, busy background, dark background"
    ),
    "checkpoint": "dreamshaperXL_lightningDPMSDE.safetensors",
    # NOTE: 食物图多走几步，保证细节清晰
    "steps": 12,
    "cfg": 2.5,
}
