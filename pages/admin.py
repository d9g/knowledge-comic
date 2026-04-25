"""
知识漫画生成器 — 管理后台

NOTE: 桌面端管理界面，包含完整的设置、生成、模板管理功能
"""
import json
import os
import sys
import logging

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config import (
    STYLE_PRESETS, LLM_PROVIDERS, DEFAULT_PROVIDER, OUTPUT_DIR,
    get_all_templates, save_custom_template_meta,
    ADMIN_USERNAME, ADMIN_PASSWORD,
)
from pages.shared import (
    init_session, get_api_config, save_api_config,
    run_analyze, run_generate, run_preview,
)
from core.audit import log_visit, log_action, log_auth

logger = logging.getLogger(__name__)

init_session()
log_visit("admin")

# NOTE: 隐藏 Streamlit 默认的多页面导航菜单
st.markdown("""
<style>
    [data-testid="stSidebarNav"] { display: none; }
</style>
""", unsafe_allow_html=True)

# ── Admin 密码保护 ──
# NOTE: ADMIN_PASSWORD 为空时不需要密码（本地开发模式）
if ADMIN_PASSWORD:
    if not st.session_state.get("admin_authenticated", False):
        st.markdown("## 🔐 管理后台登录")
        with st.form("admin_login"):
            input_user = st.text_input("用户名", key="login_user")
            input_pass = st.text_input("密码", type="password", key="login_pass")
            submitted = st.form_submit_button("登录", use_container_width=True)
            if submitted:
                if input_user == ADMIN_USERNAME and input_pass == ADMIN_PASSWORD:
                    st.session_state["admin_authenticated"] = True
                    log_auth("admin_login", True, input_user)
                    st.rerun()
                else:
                    log_auth("admin_login", False, input_user)
                    st.error("❌ 用户名或密码错误")
        st.stop()

st.markdown("## ⚙️ 管理后台")
st.markdown("[← 返回首页](/)", unsafe_allow_html=True)

# ── 侧边栏：完整设置 ──
with st.sidebar:
    st.header("⚙️ 设置")
    st.subheader("📋 模板 & 画风")

    # NOTE: 使用动态模板列表（下拉菜单）
    all_templates = get_all_templates()

    template_choice = st.selectbox(
        "模板选择",
        options=["auto"] + list(all_templates.keys()),
        format_func=lambda x: "🤖 自动匹配" if x == "auto" else all_templates.get(x, {}).get("name", x),
        index=0,
        key="admin_template",
    )

    style_choice = st.selectbox(
        "画风",
        options=list(STYLE_PRESETS.keys()),
        format_func=lambda x: STYLE_PRESETS[x]["name"],
        index=0,
        key="admin_style",
    )

    st.divider()
    st.subheader("🤖 大模型配置")

    api_cfg = get_api_config()
    provider_keys = list(LLM_PROVIDERS.keys())
    cur_idx = provider_keys.index(api_cfg["provider"]) if api_cfg["provider"] in provider_keys else 0

    provider_choice = st.selectbox(
        "模型提供商",
        options=provider_keys,
        index=cur_idx,
        format_func=lambda x: LLM_PROVIDERS[x]["name"],
        key="admin_provider",
    )
    provider_info = LLM_PROVIDERS[provider_choice]

    api_key = st.text_input(
        "API Key",
        value=api_cfg["api_key"],
        type="password",
        key="admin_api_key",
    )

    if provider_choice == "custom":
        selected_base_url = st.text_input(
            "API Base URL", value=api_cfg["base_url"],
            placeholder="https://your-api.com/v1", key="admin_base_url",
        )
        selected_model = st.text_input(
            "模型名称", value=api_cfg["model"],
            placeholder="model-name", key="admin_model",
        )
    else:
        model_list = provider_info.get("models", [])
        default_model = provider_info.get("default_model", "")
        default_model_idx = model_list.index(api_cfg["model"]) if api_cfg["model"] in model_list else (
            model_list.index(default_model) if default_model in model_list else 0
        )
        selected_model = st.selectbox("模型", options=model_list, index=default_model_idx, key="admin_model_sel")
        selected_base_url = provider_info["base_url"]

    if st.button("💾 保存", key="admin_save_settings"):
        save_api_config(provider_choice, api_key, selected_base_url, selected_model)
        st.success("✅ 已保存")

# ── 标签页 ──
tab_generate, tab_template = st.tabs(["🎨 生成漫画", "📐 模板管理"])

# ══════════════════════════════════════
# 标签1：生成漫画
# ══════════════════════════════════════
with tab_generate:
    st.subheader("📝 第1步：输入主题 → AI 生成内容")
    user_text = st.text_area(
        "输入主题或粘贴知识文案",
        height=150,
        placeholder="例如：\n气血不足最怕四个动作\n或者直接粘贴完整文案",
        key="admin_text",
    )
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        analyze_btn = st.button("🤖 AI 分析内容", type="primary", use_container_width=True, key="admin_analyze")
    with col_btn2:
        clear_btn = st.button("🗑️ 清除", use_container_width=True, key="admin_clear")

    if clear_btn:
        for k in ["admin_comic_data", "admin_comic_edited"]:
            if k in st.session_state:
                del st.session_state[k]
        st.rerun()

    if analyze_btn:
        if not user_text.strip():
            st.error("请输入主题或文案")
        elif not api_key:
            st.error("请填写 API Key")
        else:
            tpl_override = "" if template_choice == "auto" else template_choice
            with st.spinner("AI 正在分析内容..."):
                log_action("admin_analyze", user_text[:50])
                data = run_analyze(
                    user_text, api_key,
                    selected_base_url, selected_model,
                    template_override=tpl_override,
                )
                if data:
                    st.session_state["admin_comic_data"] = data
                    st.session_state["admin_comic_edited"] = json.dumps(data, ensure_ascii=False, indent=2)

    if "admin_comic_data" in st.session_state:
        st.divider()
        st.subheader("✏️ 第2步：审核修改 → 生成")
        data = st.session_state["admin_comic_data"]

        col_info1, col_info2 = st.columns([1, 1])
        with col_info1:
            tpl_name = all_templates.get(data.get("template", ""), {}).get("name", data.get("template", ""))
            st.metric("模板", tpl_name)
        with col_info2:
            st.metric("标题", data.get("title", ""))

        edited_json = st.text_area(
            "JSON 内容",
            value=st.session_state.get("admin_comic_edited", ""),
            height=400,
            label_visibility="collapsed",
            key="admin_json",
        )
        st.session_state["admin_comic_edited"] = edited_json

        col_gen, col_pv = st.columns([1, 1])
        with col_gen:
            gen_btn = st.button("🎨 确认生成图片", type="primary", use_container_width=True, key="admin_gen")
        with col_pv:
            pv_btn = st.button("👀 仅预览布局", use_container_width=True, key="admin_preview")

        preview_area = st.empty()
        action = "generate" if gen_btn else ("preview" if pv_btn else None)

        if action:
            try:
                final_data = json.loads(edited_json)
            except json.JSONDecodeError:
                st.error("🔴 JSON 格式错误")
                final_data = None

            if final_data:
                if template_choice != "auto":
                    final_template = template_choice
                    final_data["template"] = template_choice
                else:
                    final_template = final_data.get("template", "cute_panels")

                if action == "generate":
                    log_action("admin_generate", f"tpl={final_template} style={style_choice}")
                    png_bytes = run_generate(final_data, final_template, style_choice, preview_area)
                    if png_bytes:
                        st.download_button(
                            "📥 下载", data=png_bytes,
                            file_name=f"comic_{final_data.get('title', 'out')}.png",
                            mime="image/png", use_container_width=True, key="admin_dl",
                        )
                elif action == "preview":
                    run_preview(final_data, final_template, preview_area)

# ══════════════════════════════════════
# 标签2：模板管理
# ══════════════════════════════════════
with tab_template:
    st.subheader("📐 从设计图生成模板")
    st.caption("上传设计图 → AI 解析布局 → 生成 HTML 模板")

    col_upload, col_tpl_pv = st.columns([1, 1])
    with col_upload:
        uploaded_file = st.file_uploader(
            "上传设计图", type=["png", "jpg", "jpeg", "webp"],
            key="admin_upload",
        )
        if uploaded_file:
            st.image(uploaded_file, caption="上传的设计图", use_container_width=True)
        tpl_analyze_btn = st.button("🔍 AI 解析模板", type="primary", use_container_width=True, key="admin_tpl_analyze")

    with col_tpl_pv:
        st.markdown("**模板预览**")
        tpl_pv = st.empty()
        tpl_pv.info("上传设计图后点击解析")

    if tpl_analyze_btn:
        if not uploaded_file:
            st.error("请先上传设计图")
        elif not api_key:
            st.error("请填写 API Key")
        else:
            tpl_progress = st.progress(0, text="AI 正在分析设计图...")
            try:
                from core.template_analyzer import analyze_design_image, validate_jinja2_syntax
                image_bytes = uploaded_file.read()
                html_code = analyze_design_image(
                    image_bytes=image_bytes, api_key=api_key,
                    base_url=selected_base_url, model=selected_model,
                )
                tpl_progress.progress(60, text="校验模板语法...")

                # NOTE: 显示语法校验结果
                is_valid, error_msg = validate_jinja2_syntax(html_code)
                if not is_valid:
                    st.warning(f"⚠️ 模板语法存在问题（已自动修复部分）：{error_msg}")

                st.session_state["pending_template_html"] = html_code

                tpl_progress.progress(70, text="渲染预览...")
                from core.comic_renderer import render_preview
                from config import COMIC_TEMPLATES_DIR
                sample_data = {
                    "title": "示例标题",
                    "panels": [
                        {"heading": "要点一", "text": "第一个知识点", "image_path": "", "icons": ["✨"]},
                        {"heading": "要点二", "text": "第二个知识点", "image_path": "", "icons": ["🌿"]},
                        {"heading": "要点三", "text": "第三个知识点", "image_path": "", "icons": ["🎯"]},
                        {"heading": "要点四", "text": "第四个知识点", "image_path": "", "icons": ["🔥"]},
                    ],
                    "footer": "示例底部",
                    "mascot_image": "",
                }
                tmp_path = COMIC_TEMPLATES_DIR / "_preview_custom.html"
                tmp_path.write_text(html_code, encoding="utf-8")
                try:
                    png = render_preview("_preview_custom", sample_data)
                    tpl_pv.image(png, use_container_width=True)
                except Exception as err:
                    tpl_pv.warning(f"预览渲染失败: {err}")
                    logger.exception("模板预览渲染失败")
                tpl_progress.progress(100, text="完成！")
                with st.expander("HTML 源码"):
                    st.code(html_code, language="html")

            except TimeoutError as e:
                st.error(f"⏰ {e}")
            except Exception as e:
                st.error(f"🔴 解析失败: {e}")
                logger.exception("模板解析失败")

    if "pending_template_html" in st.session_state:
        st.divider()
        st.subheader("💾 保存模板")
        tpl_name = st.text_input("模板名称（英文）", placeholder="my_custom_template", key="admin_tpl_name")
        tpl_display = st.text_input("显示名称（中文）", placeholder="我的自定义模板", key="admin_tpl_display")
        tpl_desc = st.text_input("模板描述", placeholder="适合xx场景", key="admin_tpl_desc")

        if st.button("✅ 确认保存", type="primary", key="admin_tpl_save"):
            if not tpl_name:
                st.error("请输入模板名称")
            else:
                from core.template_analyzer import save_template
                from config import COMIC_TEMPLATES_DIR
                saved_path = save_template(tpl_name, st.session_state["pending_template_html"], str(COMIC_TEMPLATES_DIR))

                # NOTE: 同时保存模板元数据到清单，确保重启后仍在列表中
                save_custom_template_meta(
                    template_id=tpl_name.lower().replace(" ", "_"),
                    display_name=tpl_display,
                    description=tpl_desc,
                )

                st.success(f"✅ 已保存: {saved_path}")
                log_action("save_template", tpl_name)
                del st.session_state["pending_template_html"]
                try:
                    (COMIC_TEMPLATES_DIR / "_preview_custom.html").unlink()
                except OSError:
                    pass
