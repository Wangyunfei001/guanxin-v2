"""签名密钥解析模块。

密钥来源按优先级解析：

1. ``SECRET_KEY`` 环境变量——但内置默认值视为「未配置」；
2. 持久化文件 ``<数据目录>/.secret_key``；
3. 随机生成 48 字节并原子写入该文件。

这样仓库里不再存在任何可被公开利用的固定密钥：即使部署时忘记配置
SECRET_KEY，每个环境也会得到一把独立且持久的随机密钥。

非 development / test 环境若检测到仍然使用内置默认值，或显式配置的
密钥过短，:func:`ensure_secret_key` 会拒绝启动。
"""

from __future__ import annotations

import logging
import os
import secrets
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# 历史内置默认值。它曾随仓库公开，必须被视为「未配置」。
DEFAULT_SECRET_KEY = "guanxin-v2-dev-secret-key-change-in-production"

# 允许使用内置默认值的环境（本地开发与自动化测试）。
RELAXED_ENVIRONMENTS = frozenset({"development", "test"})

# 非开发环境要求的最小密钥长度。
MIN_SECRET_KEY_LENGTH = 32

SECRET_KEY_FILENAME = ".secret_key"

# 进程内缓存：同一进程必须始终使用同一把密钥。
_resolved_secret_key: str | None = None


def secret_key_path() -> Path:
    """返回持久化密钥文件路径（与业务数据库同目录）。"""
    return settings.business_database_path.parent / SECRET_KEY_FILENAME


def _read_persisted_key(path: Path) -> str | None:
    """读取持久化的密钥文件；不存在或内容为空时返回 None。"""
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning("读取签名密钥文件失败，将重新生成: %s", exc)
        return None
    return value or None


def _write_persisted_key(path: Path, value: str) -> None:
    """原子写入密钥文件并限制文件权限。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(value, encoding="utf-8")
    try:
        os.chmod(temporary, 0o600)
    except OSError:  # pragma: no cover - 某些文件系统不支持 chmod
        logger.warning("无法设置密钥文件权限 %s", temporary)
    os.replace(temporary, path)


def resolve_secret_key() -> str:
    """解析本次进程使用的签名密钥。

    顺序：显式配置（非默认值）→ 持久化文件 → 随机生成并持久化。
    """
    global _resolved_secret_key
    if _resolved_secret_key is not None:
        return _resolved_secret_key

    configured = settings.secret_key.strip()
    if configured and configured != DEFAULT_SECRET_KEY:
        _resolved_secret_key = configured
        return _resolved_secret_key

    path = secret_key_path()
    persisted = _read_persisted_key(path)
    if persisted:
        _resolved_secret_key = persisted
        return _resolved_secret_key

    generated = secrets.token_urlsafe(48)
    try:
        _write_persisted_key(path, generated)
    except OSError as exc:
        # 无法持久化时仍然可用，只是重启后密钥会变化。
        logger.warning("签名密钥持久化失败（%s），重启后令牌将失效", exc)
    else:
        logger.info("已生成新的签名密钥并持久化到 %s", path)
    _resolved_secret_key = generated
    return _resolved_secret_key


def reset_secret_key_cache() -> None:
    """清除进程内缓存（仅供测试使用）。"""
    global _resolved_secret_key
    _resolved_secret_key = None


def ensure_secret_key() -> str:
    """启动时校验密钥策略，不满足要求则抛出异常阻止启动。

    - 显式配置为内置默认值：开发/测试环境放行并告警，其余环境拒绝启动。
    - 显式配置的密钥过短：仅非开发环境拒绝启动。
    """
    configured = settings.secret_key.strip()
    environment = settings.app_env.strip().lower()
    relaxed = environment in RELAXED_ENVIRONMENTS

    if configured == DEFAULT_SECRET_KEY:
        if not relaxed:
            raise RuntimeError(
                "SECRET_KEY 仍是内置默认值，必须配置独立密钥后再启动。"
                "可留空 SECRET_KEY 让服务自动生成并持久化到 "
                f"{secret_key_path()}。"
            )
        logger.warning(
            "SECRET_KEY 使用的是内置默认值，仅允许用于 %s 环境；"
            "部署前请配置独立密钥。",
            environment,
        )

    if configured and not relaxed and len(configured) < MIN_SECRET_KEY_LENGTH:
        raise RuntimeError(
            f"SECRET_KEY 长度不足 {MIN_SECRET_KEY_LENGTH} 个字符，无法用于 "
            f"{environment} 环境。"
        )

    return resolve_secret_key()
