"""签名密钥策略测试。

覆盖：默认值不再可用、随机密钥持久化、非开发环境 fail-fast。
"""

import json
import os
from pathlib import Path

import pytest
from jose import jwt

from app.config import settings
from app.core import secret as secret_module
from app.core.security import create_access_token, decode_access_token


@pytest.fixture(autouse=True)
def _reset_secret_cache():
    """每个用例前后都清掉进程内密钥缓存。"""
    secret_module.reset_secret_key_cache()
    yield
    secret_module.reset_secret_key_cache()


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    """把密钥持久化目录指向临时目录。"""
    monkeypatch.setattr(settings, "database_path", str(tmp_path / "guanxin.db"))
    monkeypatch.setattr(settings, "secret_key", "")
    return tmp_path


class TestSecretKeyResolution:
    """密钥解析行为。"""

    def test_empty_config_generates_random_key(self, isolated_data_dir):
        """未配置密钥时生成随机密钥，而不是回退到内置默认值。"""
        resolved = secret_module.resolve_secret_key()
        assert resolved
        assert resolved != secret_module.DEFAULT_SECRET_KEY
        assert len(resolved) >= 32

    def test_generated_key_is_persisted(self, isolated_data_dir):
        """生成的密钥被原子写入 <数据目录>/.secret_key。"""
        resolved = secret_module.resolve_secret_key()
        key_file = isolated_data_dir / ".secret_key"
        assert key_file.exists()
        assert key_file.read_text(encoding="utf-8").strip() == resolved

    def test_persisted_key_is_reused(self, isolated_data_dir):
        """清掉缓存后重新解析，得到同一把密钥。"""
        first = secret_module.resolve_secret_key()
        secret_module.reset_secret_key_cache()
        second = secret_module.resolve_secret_key()
        assert first == second

    def test_key_file_permissions_are_restricted(self, isolated_data_dir):
        """密钥文件权限收敛到 0600。"""
        secret_module.resolve_secret_key()
        key_file = isolated_data_dir / ".secret_key"
        mode = key_file.stat().st_mode & 0o777
        assert mode == 0o600, f"期望 0600，实际 {oct(mode)}"

    def test_explicit_configuration_wins(self, isolated_data_dir, monkeypatch):
        """显式配置的密钥优先于持久化文件。"""
        secret_module.resolve_secret_key()
        monkeypatch.setattr(settings, "secret_key", "explicit-key-from-environment")
        secret_module.reset_secret_key_cache()
        assert secret_module.resolve_secret_key() == "explicit-key-from-environment"

    def test_builtin_default_is_never_used_for_signing(self, isolated_data_dir, monkeypatch):
        """即使环境变量里写着内置默认值，也会被当作未配置。"""
        monkeypatch.setattr(settings, "secret_key", secret_module.DEFAULT_SECRET_KEY)
        resolved = secret_module.resolve_secret_key()
        assert resolved != secret_module.DEFAULT_SECRET_KEY


class TestSecretKeyPolicy:
    """启动时的密钥策略校验。"""

    def test_production_rejects_builtin_default(self, monkeypatch):
        """非开发环境使用内置默认值时拒绝启动。"""
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "secret_key", secret_module.DEFAULT_SECRET_KEY)
        with pytest.raises(RuntimeError, match="内置默认值"):
            secret_module.ensure_secret_key()

    def test_production_rejects_short_key(self, monkeypatch):
        """非开发环境的密钥过短时拒绝启动。"""
        monkeypatch.setattr(settings, "app_env", "production")
        monkeypatch.setattr(settings, "secret_key", "too-short")
        with pytest.raises(RuntimeError, match="长度不足"):
            secret_module.ensure_secret_key()

    def test_development_allows_builtin_default(self, monkeypatch):
        """开发环境不因内置默认值而拒绝启动，但仍不使用它签名。"""
        monkeypatch.setattr(settings, "app_env", "development")
        monkeypatch.setattr(settings, "secret_key", secret_module.DEFAULT_SECRET_KEY)
        resolved = secret_module.ensure_secret_key()
        assert resolved
        assert resolved != secret_module.DEFAULT_SECRET_KEY

    def test_production_accepts_generated_key(self, isolated_data_dir, monkeypatch):
        """非开发环境使用自动生成的密钥可以正常启动。"""
        monkeypatch.setattr(settings, "app_env", "production")
        assert secret_module.ensure_secret_key()


class TestForgedTokenRejected:
    """回归：用公开的旧默认值伪造令牌必须失败。"""

    def test_token_signed_with_public_default_is_rejected(self, isolated_data_dir):
        """仓库中曾公开的内置默认值不能再签发有效令牌。"""
        forged = jwt.encode(
            {
                "sub": "admin-001",
                "tenant_id": "tenant-a",
                "role": "admin",
                "exp": 4_102_444_800,
            },
            secret_module.DEFAULT_SECRET_KEY,
            algorithm="HS256",
        )
        assert decode_access_token(forged) is None

    def test_round_trip_with_resolved_key(self, isolated_data_dir):
        """用解析出的密钥签发与校验的令牌可以正常工作。"""
        token = create_access_token({"sub": "admin-001", "tenant_id": "tenant-a"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "admin-001"
        assert payload["tenant_id"] == "tenant-a"


def test_builtin_default_is_not_in_repository():
    """仓库内不再以默认值形式分发该密钥（.env.example 必须留空）。"""
    example = Path(__file__).resolve().parent.parent / ".env.example"
    content = example.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("SECRET_KEY="):
            assert line.split("=", 1)[1].strip() == "", ".env.example 不得预置 SECRET_KEY"
            return
    pytest.fail(".env.example 缺少 SECRET_KEY 配置项")
