"""
知识漫画生成器 — 访问审计日志

NOTE: 记录访问者 IP、操作类型、关键参数等信息
用于安全审计和运营分析
"""
import logging
import os
import time
from datetime import datetime
from pathlib import Path

# NOTE: 审计日志独立文件，不混入应用日志
_AUDIT_DIR = Path(__file__).parent.parent / "logs"
_AUDIT_DIR.mkdir(exist_ok=True)

_audit_logger = logging.getLogger("audit")
_audit_logger.setLevel(logging.INFO)
# 避免重复添加 handler
if not _audit_logger.handlers:
    handler = logging.FileHandler(
        str(_AUDIT_DIR / "audit.log"),
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _audit_logger.addHandler(handler)


def _get_client_ip() -> str:
    """
    获取访问者真实 IP

    NOTE: Streamlit 在反向代理（nginx/frp）后面时，
    真实 IP 在 X-Forwarded-For 或 X-Real-Ip 头中。
    直连时使用 Remote-Addr。
    """
    try:
        import streamlit as st
        headers = st.context.headers
        # NOTE: 反向代理链中，X-Forwarded-For 第一个是真实客户端 IP
        forwarded = headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
        real_ip = headers.get("X-Real-Ip", "")
        if real_ip:
            return real_ip
        return headers.get("Remote-Addr", "unknown")
    except Exception:
        return "unknown"


def _get_user_agent() -> str:
    """获取访问者 User-Agent"""
    try:
        import streamlit as st
        return st.context.headers.get("User-Agent", "unknown")
    except Exception:
        return "unknown"


def log_visit(page: str) -> None:
    """
    记录页面访问

    @param page: 页面名称（generate / admin）
    """
    ip = _get_client_ip()
    ua = _get_user_agent()
    _audit_logger.info("VISIT | ip=%s | page=%s | ua=%s", ip, page, ua)


def log_action(action: str, detail: str = "") -> None:
    """
    记录用户操作

    @param action: 操作类型（analyze / generate / preview / save_template 等）
    @param detail: 附加信息（如主题、模板名等）
    """
    ip = _get_client_ip()
    _audit_logger.info("ACTION | ip=%s | action=%s | detail=%s", ip, action, detail)


def log_auth(event: str, success: bool, username: str = "") -> None:
    """
    记录认证事件

    @param event: 事件类型（admin_login / wechat_verify）
    @param success: 是否成功
    @param username: 用户名（admin 登录时）
    """
    ip = _get_client_ip()
    status = "SUCCESS" if success else "FAILED"
    _audit_logger.info(
        "AUTH | ip=%s | event=%s | status=%s | user=%s",
        ip, event, status, username,
    )


def log_error(action: str, error: str) -> None:
    """
    记录错误事件

    @param action: 发生错误的操作
    @param error: 错误信息
    """
    ip = _get_client_ip()
    _audit_logger.info("ERROR | ip=%s | action=%s | error=%s", ip, action, error)
