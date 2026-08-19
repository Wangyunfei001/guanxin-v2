"""应用配置模块。

使用 pydantic-settings 从环境变量加载配置，
提供全局 Settings 单例。
"""

from pathlib import Path
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局应用配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # === 应用配置 ===
    app_name: str = "观心 v2"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # === 安全配置 ===
    secret_key: str = "guanxin-v2-dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # === 数据库 ===
    chroma_persist_dir: str = "./data/chroma"

    # === LLM 配置 ===
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    # === Embedding 配置 ===
    embedding_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-v3"

    # === 文件上传 ===
    upload_dir: str = "./data/uploads"
    max_upload_size_mb: int = 20

    # === CORS ===
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # === Agent 配置 ===
    agent_mode: str = "state_graph"  # "state_graph" | "legacy"
    available_models: str = "deepseek-v4-flash,gpt-4o-mini,gpt-4o,deepseek-v3"
    openai_temperature: float = 0.7

    # === 预设用户 ===
    preset_users_json: str = ""

    @field_validator("cors_origins")
    @classmethod
    def validate_cors_origins(cls, v: str) -> str:
        """确保 CORS 字符串非空。"""
        if not v.strip():
            return "http://localhost:5173"
        return v

    @property
    def cors_origin_list(self) -> List[str]:
        """将逗号分隔的 CORS 字符串转为列表。"""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def available_models_list(self) -> List[str]:
        """将逗号分隔的模型列表转为列表。"""
        return [m.strip() for m in self.available_models.split(",") if m.strip()]

    @property
    def upload_path(self) -> Path:
        """上传目录 Path 对象。"""
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def chroma_path(self) -> Path:
        """ChromaDB 持久化目录 Path 对象。"""
        p = Path(self.chroma_persist_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


# 全局单例
settings = Settings()
