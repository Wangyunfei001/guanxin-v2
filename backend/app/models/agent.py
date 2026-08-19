"""Agent 模型模块。"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


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
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    tool_call_id: str = ""
    reasoning: str = ""
    a2ui_schemas: List[Dict[str, Any]] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        """转换为字典。"""
        return {
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "tool_call_id": self.tool_call_id,
            "reasoning": self.reasoning,
            "a2ui_schemas": self.a2ui_schemas,
            "created_at": self.created_at,
        }


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
    """Agent 配置存储管理器：内存存储。"""

    def __init__(self) -> None:
        self._configs: Dict[str, AgentConfig] = {}  # key: "{tenant_id}:{agent_id}"
        self._default_configs: Dict[str, AgentConfig] = {}  # key: tenant_id

    def _key(self, tenant_id: str, agent_id: str) -> str:
        return f"{tenant_id}:{agent_id}"

    def save_config(self, config: AgentConfig) -> AgentConfig:
        """保存 Agent 配置。"""
        self._configs[self._key(config.tenant_id, config.agent_id)] = config
        return config

    def get_config(self, tenant_id: str, agent_id: str) -> Optional[AgentConfig]:
        """获取 Agent 配置。"""
        return self._configs.get(self._key(tenant_id, agent_id))

    def list_configs(self, tenant_id: str) -> List[AgentConfig]:
        """列出租户的所有 Agent 配置。"""
        return [
            c for k, c in self._configs.items() if k.startswith(f"{tenant_id}:")
        ]

    def delete_config(self, tenant_id: str, agent_id: str) -> bool:
        """删除 Agent 配置。"""
        key = self._key(tenant_id, agent_id)
        if key in self._configs:
            del self._configs[key]
            return True
        return False

    def get_or_create_default(self, tenant_id: str) -> AgentConfig:
        """获取或创建默认 Agent 配置。"""
        if tenant_id in self._default_configs:
            return self._default_configs[tenant_id]
        config = AgentConfig(
            agent_id="default",
            tenant_id=tenant_id,
            name="默认助手",
            description="观心 v2 默认 AI 助手",
            system_prompt="你是观心 v2 的 AI 助手，可以帮助用户管理知识库、分析数据、回答问题。请友善、专业地回答用户的问题。",
        )
        self._default_configs[tenant_id] = config
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
