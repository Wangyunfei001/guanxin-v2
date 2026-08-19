"""对话存储模块。

管理对话历史和消息记录，内存存储。
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.agent import Conversation, ConversationMessage


class ConversationStore:
    """对话存储管理器：内存存储。"""

    def __init__(self) -> None:
        self._conversations: Dict[str, Conversation] = {}  # key: conversation_id

    def create_conversation(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str,
        title: str = "",
    ) -> Conversation:
        """创建新对话。"""
        conversation_id = str(uuid.uuid4())
        conv = Conversation(
            conversation_id=conversation_id,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            title=title or "新对话",
        )
        self._conversations[conversation_id] = conv
        return conv

    def get_conversation(
        self, conversation_id: str, tenant_id: str
    ) -> Optional[Conversation]:
        """获取对话（带租户校验）。"""
        conv = self._conversations.get(conversation_id)
        if conv and conv.tenant_id == tenant_id:
            return conv
        return None

    def list_conversations(self, tenant_id: str, user_id: str = "") -> List[Conversation]:
        """列出对话。"""
        result = []
        for conv in self._conversations.values():
            if conv.tenant_id != tenant_id:
                continue
            if user_id and conv.user_id != user_id:
                continue
            result.append(conv)
        return result

    def add_message(
        self, conversation_id: str, message: ConversationMessage
    ) -> Optional[Conversation]:
        """添加消息到对话。"""
        conv = self._conversations.get(conversation_id)
        if conv is None:
            return None
        conv.messages.append(message)
        conv.updated_at = datetime.now(timezone.utc).isoformat()
        return conv

    def delete_conversation(self, conversation_id: str, tenant_id: str) -> bool:
        """删除对话。"""
        conv = self._conversations.get(conversation_id)
        if conv and conv.tenant_id == tenant_id:
            del self._conversations[conversation_id]
            return True
        return False

    def get_messages(
        self, conversation_id: str, tenant_id: str
    ) -> List[ConversationMessage]:
        """获取对话消息列表。"""
        conv = self.get_conversation(conversation_id, tenant_id)
        if conv is None:
            return []
        return conv.messages


# 全局单例
_conversation_store: Optional[ConversationStore] = None


def get_conversation_store() -> ConversationStore:
    """获取全局对话存储单例。"""
    global _conversation_store
    if _conversation_store is None:
        _conversation_store = ConversationStore()
    return _conversation_store


def reset_conversation_store() -> None:
    """重置对话存储（用于测试）。"""
    global _conversation_store
    _conversation_store = None
