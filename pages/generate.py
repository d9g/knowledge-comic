"""
知识漫画生成器 — 首页（手机端适配）

NOTE: 这是默认首页，专为移动端触摸交互优化，
桌面端用户可以通过设置面板进入管理后台。
"""
import json
import os
import sys
import logging

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import STYLE_PRESETS, get_all_templates, REQUIRE_WECHAT_FOLLOW, WECHAT_FOLLOW_GUIDE, get_random_footer
from core.audit import log_visit, log_action, log_auth
from pages.shared import (
    init_session, get_api_config, save_api_config,
    run_analyze, run_generate, run_preview,
)

logger = logging.getLogger(__name__)

init_session()
log_visit("generate")

# ── 手机端适配 CSS ──
st.markdown("""
<style>
    /* 隐藏 Streamlit 默认导航 */
    [data-testid="stSidebarNav"] { display: none; }
    header[data-testid="stHeader"] { display: none; }

    /* 手机端：单列、全宽、大字体 */
    .stApp { max-width: 100%; padding: 0; }
    .block-container {
        max-width: 600px !important;
        margin: 0 auto;
        padding: 1rem 0.8rem !important;
    }

    /* 标题居中 */
    .app-header {
        text-align: center;
        padding: 0.8rem 0 0.3rem 0;
    }
    .app-header h1 {
        font-size: 1.6em;
        margin: 0;
    }
    .app-header p {
        color: #888;
        font-size: 0.85em;
        margin: 0.2em 0 0 0;
    }

    /* 大按钮（触摸友好） */
    .stButton > button {
        min-height: 48px;
        font-size: 1em;
        border-radius: 12px;
    }

    /* 文本框字体 */
    .stTextArea textarea {
        font-size: 1em;
        line-height: 1.5;
    }

    /* 步骤分隔 */
    .step-label {
        font-size: 0.85em;
        color: #666;
        font-weight: 600;
        margin: 0.8rem 0 0.3rem 0;
        padding: 0.3rem 0.6rem;
        background: #f0f0f0;
        border-radius: 8px;
        display: inline-block;
    }

    /* 下载按钮区域 */
    .stDownloadButton > button {
        min-height: 52px;
        font-size: 1.1em;
    }

    /* 文件上传区域优化（手机端更大的点击区域） */
    [data-testid="stFileUploader"] {
        min-height: 80px;
    }
    [data-testid="stFileUploader"] button {
        min-height: 48px !important;
        font-size: 1em !important;
    }
</style>
""", unsafe_allow_html=True)

# ── 顶部标题 ──
st.markdown("""
<div class="app-header">
    <h1>📚 知识漫画生成器</h1>
    <p>输入主题 → AI 生成内容 → 一键出图</p>
</div>
""", unsafe_allow_html=True)

# ── 获取当前 API 配置 ──
api_cfg = get_api_config()

# ── 微信关注门控 ──
# NOTE: REQUIRE_WECHAT_FOLLOW=true 时，需输入使用码才能继续
# 具体验证逻辑（调微信 API 等）后续扩展，当前用本地验证码占位
if REQUIRE_WECHAT_FOLLOW and not st.session_state.get("wechat_verified", False):
    st.info(f"🔒 {WECHAT_FOLLOW_GUIDE}")
    with st.form("wechat_verify"):
        verify_code = st.text_input("请输入使用码", placeholder="关注公众号后获取", key="verify_code")
        if st.form_submit_button("验证", use_container_width=True):
            # TODO: 接入微信公众号 API 验证关注状态
            # 当前占位逻辑：从 .local_settings.json 中读取 activation_codes 列表进行比对
            from pages.shared import load_settings
            settings = load_settings()
            valid_codes = settings.get("activation_codes", [])
            if verify_code in valid_codes:
                st.session_state["wechat_verified"] = True
                log_auth("wechat_verify", True)
                st.rerun()
            else:
                log_auth("wechat_verify", False)
                st.error("❌ 使用码无效")
    st.stop()

# ══════════════════════════════════════
# 第1步：输入主题
# ══════════════════════════════════════
st.markdown('<div class="step-label">📝 第1步：输入主题</div>', unsafe_allow_html=True)
user_text = st.text_area(
    "输入主题或粘贴知识文案",
    height=120,
    placeholder="例如：\n气血不足最怕四个动作\n或者直接粘贴完整文案",
    label_visibility="collapsed",
    key="mobile_text",
)

analyze_btn = st.button("🤖 AI 分析内容", type="primary", use_container_width=True, key="mobile_analyze")

if analyze_btn:
    if not user_text.strip():
        st.error("请输入主题或文案")
    elif not api_cfg["api_key"]:
        st.error("请先点击 ⚙️ 设置 API Key")
    else:
        with st.spinner("AI 正在分析内容..."):
            log_action("analyze", user_text[:50])
            data = run_analyze(
                user_text, api_cfg["api_key"],
                api_cfg["base_url"], api_cfg["model"],
            )
            if data:
                st.session_state["comic_data"] = data
                st.session_state["comic_data_edited"] = json.dumps(data, ensure_ascii=False, indent=2)

# ══════════════════════════════════════
# 第2步：审核修改（表单化编辑）
# ══════════════════════════════════════
if "comic_data" in st.session_state:
    data = st.session_state["comic_data"]
    template_from_json = data.get("template", "cute_panels")

    st.markdown('<div class="step-label">✏️ 第2步：审核内容</div>', unsafe_allow_html=True)

    # ── 标题编辑 ──
    edited_title = st.text_input(
        "📝 标题",
        value=data.get("title", ""),
        max_chars=30,
        key="edit_title",
    )

    # ── 面板列表编辑 ──
    panels = data.get("panels", [])
    edited_panels = []
    for i, panel in enumerate(panels):
        with st.expander(f"📋 面板 {i + 1}：{panel.get('heading', '')}", expanded=(i == 0)):
            heading = st.text_input(
                "小标题",
                value=panel.get("heading", ""),
                max_chars=20,
                key=f"panel_heading_{i}",
            )
            text = st.text_area(
                "内容",
                value=panel.get("text", ""),
                height=80,
                key=f"panel_text_{i}",
            )
            icons_str = st.text_input(
                "图标（用空格分隔）",
                value=" ".join(panel.get("icons", [])),
                key=f"panel_icons_{i}",
            )
            edited_panels.append({
                **panel,
                "heading": heading,
                "text": text,
                "icons": [ic.strip() for ic in icons_str.split() if ic.strip()],
            })

    # ── Footer 编辑 ──
    edited_footer = st.text_input(
        "📌 底部文案",
        value=data.get("footer") or get_random_footer(),
        max_chars=50,
        key="edit_footer",
    )

    # ── 高级编辑（原始 JSON，默认折叠） ──
    with st.expander("🔧 高级：编辑原始 JSON"):
        # NOTE: 同步表单修改到 JSON
        synced_data = dict(data)
        synced_data["title"] = edited_title
        synced_data["panels"] = edited_panels
        synced_data["footer"] = edited_footer
        edited_json = st.text_area(
            "JSON",
            value=json.dumps(synced_data, ensure_ascii=False, indent=2),
            height=300,
            label_visibility="collapsed",
            key="mobile_json",
        )
        st.session_state["comic_data_edited"] = edited_json

    # ── 模板 & 画风选择 ──
    st.markdown('<div class="step-label">🎨 第3步：选择模板和画风</div>', unsafe_allow_html=True)

    all_templates = get_all_templates()

    col_tpl, col_style = st.columns([1, 1])
    with col_tpl:
        tpl_options = ["auto"] + list(all_templates.keys())
        default_tpl_idx = tpl_options.index(template_from_json) if template_from_json in tpl_options else 0
        template_choice = st.selectbox(
            "模板",
            options=tpl_options,
            index=default_tpl_idx,
            format_func=lambda x: "🤖 自动" if x == "auto" else all_templates.get(x, {}).get("name", x),
            key="mobile_template",
        )
    with col_style:
        style_choice = st.selectbox(
            "画风",
            options=list(STYLE_PRESETS.keys()),
            format_func=lambda x: STYLE_PRESETS[x]["name"],
            key="mobile_style",
        )

    # ── 操作按钮 ──
    col_gen, col_preview = st.columns([1, 1])
    with col_gen:
        gen_btn = st.button("🎨 生成图片", type="primary", use_container_width=True, key="mobile_gen")
    with col_preview:
        preview_btn = st.button("👀 预览布局", use_container_width=True, key="mobile_preview")

    if st.button("🗑️ 清除重来", use_container_width=True, key="mobile_clear"):
        for k in ["comic_data", "comic_data_edited"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    # ── 处理生成/预览 ──
    preview_area = st.empty()
    action = "generate" if gen_btn else ("preview" if preview_btn else None)

    if action:
        # NOTE: 优先从表单构造数据，回退到 JSON 编辑器
        try:
            if "comic_data_edited" in st.session_state:
                final_data = json.loads(st.session_state["comic_data_edited"])
            else:
                final_data = dict(data)
                final_data["title"] = edited_title
                final_data["panels"] = edited_panels
                final_data["footer"] = edited_footer
        except json.JSONDecodeError:
            st.error("🔴 JSON 格式错误")
            final_data = None

        if final_data:
            # NOTE: 安全过滤所有用户输入
            from core.sanitizer import sanitize_comic_data
            final_data = sanitize_comic_data(final_data)

            # 确定模板
            if template_choice != "auto":
                final_template = template_choice
                final_data["template"] = template_choice
            else:
                final_template = final_data.get("template", "cute_panels")

            if action == "generate":
                log_action("generate", f"tpl={final_template} style={style_choice}")
                png_bytes = run_generate(final_data, final_template, style_choice, preview_area)
                if png_bytes:
                    st.download_button(
                        label="📥 下载长图", data=png_bytes,
                        file_name=f"comic_{final_data.get('title', 'output')}.png",
                        mime="image/png", use_container_width=True,
                        key="mobile_download",
                    )
            elif action == "preview":
                log_action("preview", f"tpl={final_template}")
                run_preview(final_data, final_template, preview_area)

