@echo off
chcp 65001 >nul
title 知识漫画生成器

REM NOTE: 自动定位到脚本所在目录（不依赖硬编码路径）
cd /d "%~dp0"

echo ========================================
echo   知识漫画生成器 — 本地启动
echo ========================================
echo.

echo [1/3] 检查依赖...
python -c "import jinja2, playwright, streamlit, openai, httpx" 2>nul
if errorlevel 1 (
    echo 安装依赖...
    pip install -r requirements.txt
    playwright install chromium
)
echo 依赖 OK.
echo.

echo [2/3] 检查 cryptography（可选）...
python -c "import cryptography" 2>nul
if errorlevel 1 (
    echo 安装 cryptography（API Key 加密）...
    pip install "cryptography>=42.0.0"
)
echo.

echo [3/3] 启动 Streamlit 服务...
echo 地址: http://localhost:8550
echo.
python -m streamlit run app.py --server.port 8550
