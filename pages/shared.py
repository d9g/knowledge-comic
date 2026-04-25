"""
知识漫画生成器 — 共享工具（多页面公用）

NOTE: 统一管理 Session 初始化、API 配置、
以及 generate/admin 两个页面共用的生成逻辑。
"""
import json
import logging
import os
import sys
import time

import streamlit as st

# NOTE: 确保项目根目录在 Python 路径中
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    LLM_PROVIDERS, DEFAULT_PROVIDER, OUTPUT_DIR, BASE_DIR,
)
from core.crypto_utils import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

SETTINGS_FILE = BASE_DIR / ".local_settings.json"


def load_settings() -> dict:
    """从本地文件加载设置"""
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_settings(settings: dict) -> None:
    """保存设置到本地文件"""
    try:
        SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning("Save settings failed: %s", e)


def init_session():
    """初始化 session_state 中的共享数据"""
    if "local_settings" not in st.session_state:
        st.session_state["local_settings"] = load_settings()


def get_api_config() -> dict:
    """
    从 session_state 获取当前 API 配置

    NOTE: API Key 从加密存储中解密读取

    @returns: {"api_key", "base_url", "model", "provider"}
    """
    init_session()
    settings = st.session_state["local_settings"]

    provider = settings.get("provider", DEFAULT_PROVIDER)
    provider_info = LLM_PROVIDERS.get(provider, LLM_PROVIDERS[DEFAULT_PROVIDER])

    env_key_name = provider_info.get("env_key", "")
    # NOTE: 从加密字段读取并解密
    saved_key_encrypted = settings.get(f"api_key_{provider}", "")
    saved_key = decrypt_value(saved_key_encrypted)
    env_key = os.environ.get(env_key_name, "") if env_key_name else ""

    return {
        "api_key": saved_key or env_key,
        "base_url": settings.get("base_url", provider_info.get("base_url", "")),
        "model": settings.get("model", provider_info.get("default_model", "")),
        "provider": provider,
    }


def save_api_config(provider: str, api_key: str, base_url: str, model: str) -> None:
    """
    保存 API 配置

    NOTE: API Key 加密后存储，不再明文保存
    """
    init_session()
    settings = st.session_state["local_settings"]
    settings["provider"] = provider
    # NOTE: 加密存储 API Key
    settings[f"api_key_{provider}"] = encrypt_value(api_key)
    settings["base_url"] = base_url
    settings["model"] = model
    st.session_state["local_settings"] = settings
    save_settings(settings)


# ══════════════════════════════════════
# 共享生成逻辑——消除 generate.py 和 admin.py 的代码重复
# ══════════════════════════════════════


def run_analyze(
    user_text: str,
    api_key: str,
    base_url: str,
    model: str,
    template_override: str = "",
) -> dict | None:
    """
    执行 AI 文案分析，统一错误处理

    @returns: 分析结果字典，失败返回 None
    """
    try:
        from core.comic_generator import analyze_content
        data = analyze_content(
            text=user_text,
            api_key=api_key,
            base_url=base_url,
            model=model,
            template_override=template_override,
        )
        st.success("✅ AI 分析完成！")
        return data
    except TimeoutError as e:
        st.error(f"⏰ {e}")
    except json.JSONDecodeError:
        st.error("🔴 返回内容无法解析为 JSON，请重试")
        logger.exception("JSON 解析失败")
    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "timed out" in error_msg.lower():
            st.error("⏰ AI 响应超时，请稍后重试或切换模型")
        else:
            st.error(f"🔴 分析失败: {e}")
        logger.exception("分析失败")
    return None


def run_generate(
    final_data: dict,
    final_template: str,
    style_choice: str,
    preview_area,
) -> bytes | None:
    """
    执行完整的生成流程（ComfyUI 插画 + 模板渲染），统一错误处理

    @returns: PNG 字节流，失败返回 None
    """
    progress = st.progress(0, text="开始生成...")
    try:
        import requests
        from config import COMFYUI_URL

        comfyui_online = False
        try:
            r = requests.get(f"{COMFYUI_URL}/system_stats", timeout=3)
            comfyui_online = r.status_code == 200
        except Exception:
            pass

        if comfyui_online:
            from core.comic_generator import generate_illustrations
            work_dir = str(OUTPUT_DIR / f"comic_{int(time.time())}")

            def update_progress(p: float):
                progress.progress(int(p * 80), text=f"生成插画 {int(p * 100)}%...")

            final_data = generate_illustrations(
                data=final_data, work_dir=work_dir,
                style=style_choice, progress_callback=update_progress,
            )
        else:
            st.warning("⚠ ComfyUI 未运行，使用占位图")

        progress.progress(80, text="渲染图片...")
        from core.comic_renderer import render_preview
        png_bytes = render_preview(final_template, final_data)
        preview_area.image(png_bytes, use_container_width=True)
        progress.progress(100, text="完成！")
        return png_bytes

    except TimeoutError as e:
        st.error(f"⏰ {e}")
    except Exception as e:
        st.error(f"🔴 生成失败: {e}")
        logger.exception("生成失败")
    return None


def run_preview(final_data: dict, final_template: str, preview_area) -> bytes | None:
    """
    仅渲染预览（不生成插画），统一错误处理

    @returns: PNG 字节流，失败返回 None
    """
    try:
        from core.comic_renderer import render_preview
        png_bytes = render_preview(final_template, final_data)
        preview_area.image(png_bytes, use_container_width=True)
        return png_bytes
    except Exception as e:
        st.error(f"🔴 预览失败: {e}")
        logger.exception("预览失败")
    return None
