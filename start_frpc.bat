@echo off
chcp 65001 >nul
title ComfyUI 内网穿透 (frpc)

echo ========================================
echo   ComfyUI 内网穿透客户端
echo ========================================
echo.
echo 确保以下条件：
echo   1. ComfyUI 已在本地 8188 端口运行
echo   2. frpc.toml 中已填写云服务器 IP
echo.

REM NOTE: frpc.exe 需要放在本脚本同目录
REM 下载地址: https://github.com/fatedier/frp/releases
if not exist frpc.exe (
    echo [错误] 未找到 frpc.exe，请下载 frp 并放到此目录
    echo 下载: https://github.com/fatedier/frp/releases
    pause
    exit /b 1
)

echo 启动穿透...
frpc.exe -c deploy\frpc.toml

pause
