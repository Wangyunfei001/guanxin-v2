"""Agent 模型模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional

from app.core.sqlite import connect, initialize_database, transaction


@dataclass
class AgentConfig:
    """Agent 配置模型。"""

    agent_id: str
    tenant_id: str
    name: str
    description: str = ""
    model: str = "gpt-4o-mini"
    system_prompt: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    enabled_tools: List[str] = field(default_factory=lambda: ["kb_retrieval"])
    enabled_skills: List[str] = field(default_factory=list)
    mcp_servers: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "enabled_tools": self.enabled_tools,
            "enabled_skills": self.enabled_skills,
            "mcp_servers": self.mcp_servers,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class ConversationMessage:
    """对话消息模型。"""

    role: str  # user | assistant | system | tool
    content: str
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""
    reasoning: str = ""
    a2ui_schemas: List[Dict[str, Any]] = field(default_factory=list)
    parts: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "message_id": self.message_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "reasoning": self.reasoning,
            "a2ui_schemas": self.a2ui_schemas,
            "parts": self.parts or self._default_parts(),
            "created_at": self.created_at,
        }

    def _default_parts(self) -> List[Dict[str, Any]]:
        """生成兼容 AI SDK 的基础 parts。"""
        parts: List[Dict[str, Any]] = []
        if self.reasoning:
            parts.append({"type": "reasoning", "text": self.reasoning})
        if self.content:
            parts.append({"type": "text", "text": self.content})
        parts.extend(self.tool_calls)
        parts.extend(
            {"type": "data-a2ui", "data": schema}
            for schema in self.a2ui_schemas
        )
        return parts


@dataclass
class Conversation:
    """对话模型。"""

    conversation_id: str
    tenant_id: str
    user_id: str
    agent_id: str
    title: str = ""
    messages: List[ConversationMessage] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "conversation_id": self.conversation_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "title": self.title,
            "messages": [m.to_dict() for m in self.messages],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AgentConfigStore:
    """SQLite Agent 配置存储管理器。"""

    def __init__(self) -> None:
        initialize_database()

    @staticmethod
    def _from_row(row: Any) -> AgentConfig:
        return AgentConfig(
            agent_id=row["agent_id"],
            tenant_id=row["tenant_id"],
            name=row["name"],
            description=row["description"],
            model=row["model"],
            system_prompt=row["system_prompt"],
            temperature=row["temperature"],
            max_tokens=row["max_tokens"],
            enabled_tools=json.loads(row["enabled_tools_json"] or "[]"),
            enabled_skills=json.loads(row["enabled_skills_json"] or "[]"),
            mcp_servers=json.loads(row["mcp_servers_json"] or "[]"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def save_config(self, config: AgentConfig) -> AgentConfig:
        """保存 Agent 配置。"""
        now = datetime.now(timezone.utc).isoformat()
        config.updated_at = now
        with transaction() as conn:
            conn.execute(
                """
                INSERT INTO agent_configs(
                    tenant_id, agent_id, name, description, model, system_prompt,
                    temperature, max_tokens, enabled_tools_json,
                    enabled_skills_json, mcp_servers_json, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, agent_id) DO UPDATE SET
                    name=excluded.name,
                    description=excluded.description,
                    model=excluded.model,
                    system_prompt=excluded.system_prompt,
                    temperature=excluded.temperature,
                    max_tokens=excluded.max_tokens,
                    enabled_tools_json=excluded.enabled_tools_json,
                    enabled_skills_json=excluded.enabled_skills_json,
                    mcp_servers_json=excluded.mcp_servers_json,
                    metadata_json=excluded.metadata_json,
                    updated_at=excluded.updated_at
                """,
                (
                    config.tenant_id, config.agent_id, config.name,
                    config.description, config.model, config.system_prompt,
                    config.temperature, config.max_tokens,
                    json.dumps(config.enabled_tools, ensure_ascii=False),
                    json.dumps(config.enabled_skills, ensure_ascii=False),
                    json.dumps(config.mcp_servers, ensure_ascii=False),
                    json.dumps(config.metadata, ensure_ascii=False),
                    config.created_at, config.updated_at,
                ),
            )
        return config

    def get_config(self, tenant_id: str, agent_id: str) -> Optional[AgentConfig]:
        """获取 Agent 配置。"""
        conn = connect()
        try:
            row = conn.execute(
                "SELECT * FROM agent_configs WHERE tenant_id=? AND agent_id=?",
                (tenant_id, agent_id),
            ).fetchone()
            return self._from_row(row) if row else None
        finally:
            conn.close()

    def list_configs(self, tenant_id: str) -> List[AgentConfig]:
        """列出租户的所有 Agent 配置。"""
        conn = connect()
        try:
            rows = conn.execute(
                "SELECT * FROM agent_configs WHERE tenant_id=? ORDER BY created_at",
                (tenant_id,),
            ).fetchall()
            return [self._from_row(row) for row in rows]
        finally:
            conn.close()

    def delete_config(self, tenant_id: str, agent_id: str) -> bool:
        """删除 Agent 配置。"""
        with transaction() as conn:
            cursor = conn.execute(
                "DELETE FROM agent_configs WHERE tenant_id=? AND agent_id=?",
                (tenant_id, agent_id),
            )
            return cursor.rowcount > 0

    def get_or_create_default(self, tenant_id: str) -> AgentConfig:
        """获取或创建默认 Agent 配置。"""
        existing = self.get_config(tenant_id, "default")
        if existing:
            return existing
        config = AgentConfig(
            agent_id="default",
            tenant_id=tenant_id,
            name="默认助手",
            description="观心 v2 默认 AI 助手",
            system_prompt="你是观心 v2 的 AI 助手，可以帮助用户管理知识库、分析数据、回答问题。请友善、专业地回答用户的问题。",
        )
        self.save_config(config)
        return config


# 全局单例
_agent_config_store: Optional[AgentConfigStore] = None


def get_agent_config_store() -> AgentConfigStore:
    """获取全局 Agent 配置存储单例。"""
    global _agent_config_store
    if _agent_config_store is None:
        _agent_config_store = AgentConfigStore()
    return _agent_config_store
