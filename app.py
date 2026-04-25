"""
知识漫画生成器 — 多页面入口
"""
import streamlit as st

# NOTE: 必须在最前面设置 page_config
st.set_page_config(
    page_title="知识漫画生成器",
    page_icon="📚",
    layout="wide",
)

# 多页面导航
generate_page = st.Page("pages/generate.py", title="生成漫画", icon="🎨", default=True)
admin_page = st.Page("pages/admin.py", title="管理后台", icon="⚙️")

pg = st.navigation([generate_page, admin_page], position="hidden")
pg.run()
