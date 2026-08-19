"""Seed 数据初始化模块。

幂等地初始化示例文档、默认 Agent 配置、默认 MCP Server 配置。
"""

import logging
from typing import Optional

from app.models.agent import AgentConfig, get_agent_config_store
from app.mcp.server import get_mcp_server_manager
from app.services.knowledge_service import get_knowledge_service
from app.config import settings

logger = logging.getLogger(__name__)

# 标记是否已初始化
_seed_initialized: bool = False


async def init_seed_data() -> None:
    """幂等地初始化种子数据。

    包含：
    1. 为每个租户上传示例文档
    2. 创建默认 Agent 配置
    3. 注册默认 MCP Server
    """
    global _seed_initialized
    if _seed_initialized:
        logger.info("Seed data already initialized, skipping")
        return

    logger.info("Initializing seed data...")

    # 初始化默认 MCP Server 配置
    _init_mcp_servers()

    # 初始化默认 Agent 配置
    _init_agent_configs()

    # 为预设租户上传示例文档
    await _init_seed_documents()

    _seed_initialized = True
    logger.info("Seed data initialization complete")


def _init_mcp_servers() -> None:
    """初始化默认 MCP Server 配置。"""
    from app.seed.data import SEED_MCP_SERVERS

    manager = get_mcp_server_manager()
    for config in SEED_MCP_SERVERS:
        existing = manager.get_server(config["name"])
        if existing is None:
            manager.register_server(
                name=config["name"],
                command=config["command"],
                args=config["args"],
                env=config.get("env", {}),
                description=config.get("description", ""),
            )
            logger.info(f"Registered MCP server: {config['name']}")


def _init_agent_configs() -> None:
    """初始化默认 Agent 配置。"""
    from app.seed.data import SEED_AGENT_CONFIGS

    store = get_agent_config_store()

    # 为每个预设租户创建默认 Agent
    tenant_ids = ["tenant-a", "tenant-b"]
    for tenant_id in tenant_ids:
        for config_data in SEED_AGENT_CONFIGS:
            existing = store.get_config(tenant_id, config_data["agent_id"])
            if existing is None:
                config = AgentConfig(
                    agent_id=config_data["agent_id"],
                    tenant_id=tenant_id,
                    name=config_data["name"],
                    description=config_data["description"],
                    # Match the configured gateway on first boot. Subsequent
                    # starts never overwrite an existing tenant config.
                    model=settings.openai_model,
                    system_prompt=config_data["system_prompt"],
                    temperature=config_data["temperature"],
                    max_tokens=config_data["max_tokens"],
                    enabled_tools=config_data["enabled_tools"],
                    enabled_skills=config_data["enabled_skills"],
                    mcp_servers=config_data["mcp_servers"],
                )
                store.save_config(config)
                logger.info(
                    f"Created agent config: {config.agent_id} for tenant: {tenant_id}"
                )


async def _init_seed_documents() -> None:
    """为预设租户上传示例文档。"""
    from app.models.document import DocumentStatus
    from app.models.document import get_document_store
    from app.seed.data import SEED_DOCUMENTS

    tenant_ids = ["tenant-a", "tenant-b"]
    service = get_knowledge_service()
    doc_store = get_document_store()

    for tenant_id in tenant_ids:
        existing_docs = doc_store.list_documents(tenant_id)
        if existing_docs:
            logger.info(
                f"Tenant {tenant_id} already has {len(existing_docs)} documents, skipping seed"
            )
            continue

        for doc_data in SEED_DOCUMENTS:
            try:
                content_bytes = doc_data["content"].encode("utf-8")
                doc = await service.upload_document(
                    tenant_id=tenant_id,
                    filename=doc_data["filename"],
                    content=content_bytes,
                    title=doc_data["title"],
                )
                logger.info(
                    f"Uploaded seed document: {doc.filename} (status: {doc.status.value})"
                )
            except Exception as e:
                logger.error(f"Failed to upload seed document {doc_data['filename']}: {e}")


def reset_seed_state() -> None:
    """重置 seed 状态（用于测试）。"""
    global _seed_initialized
    _seed_initialized = False
