"""
API Key 加密工具

NOTE: 使用 Fernet 对称加密保护本地存储的 API Key，
密钥派生自机器特征（用户名 + 主机名），非绝对安全但远优于明文。
"""
import base64
import hashlib
import logging
import os
import platform

logger = logging.getLogger(__name__)


def _derive_key() -> bytes:
    """
    基于机器特征生成确定性 Fernet 密钥

    NOTE: 使用用户名 + 主机名 + 固定盐值派生，
    相同机器每次生成相同密钥，换机器无法解密。
    """
    username = os.getenv("USERNAME", os.getenv("USER", "default"))
    hostname = platform.node()
    salt = "knowledge_comic_v1"
    raw = f"{username}:{hostname}:{salt}".encode("utf-8")
    # SHA-256 → 取前 32 字节 → base64 编码为 Fernet 密钥
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_value(plain_text: str) -> str:
    """
    加密字符串

    @param plain_text: 明文
    @returns: 密文（base64 字符串）
    """
    if not plain_text:
        return ""
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_derive_key())
        return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")
    except ImportError:
        # NOTE: 未安装 cryptography 时回退为 base64 编码
        logger.warning("cryptography 库未安装，使用 base64 编码（安全性较低）")
        return "b64:" + base64.b64encode(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_value(cipher_text: str) -> str:
    """
    解密字符串

    @param cipher_text: 密文
    @returns: 明文
    """
    if not cipher_text:
        return ""
    # 兼容旧版明文数据（以 sk- 开头的都是未加密的原始 Key）
    if cipher_text.startswith("sk-"):
        return cipher_text
    # base64 回退模式
    if cipher_text.startswith("b64:"):
        try:
            return base64.b64decode(cipher_text[4:]).decode("utf-8")
        except Exception:
            return cipher_text
    try:
        from cryptography.fernet import Fernet
        f = Fernet(_derive_key())
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except ImportError:
        logger.warning("cryptography 库未安装，无法解密")
        return cipher_text
    except Exception:
        # NOTE: 解密失败说明数据格式已变化，视为明文返回
        logger.warning("解密失败，视为明文")
        return cipher_text
