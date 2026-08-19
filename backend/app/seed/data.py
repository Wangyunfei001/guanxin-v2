"""Seed 数据定义模块。

包含示例文档、默认 Agent 配置、默认 MCP Server 配置等种子数据。
"""

import sys
from typing import Any, Dict, List

# === 示例文档 ===
SEED_DOCUMENTS: List[Dict[str, str]] = [
    {
        "filename": "观心v2产品介绍.txt",
        "title": "观心 v2 产品介绍",
        "content": """观心 v2 是一个 AI Agent 全栈 Demo 系统，展示了以下核心能力：

1. 多租户知识库管理：支持文档上传、自动分块、向量检索，每个租户的数据完全隔离。
2. LangGraph ReAct Agent：基于 LangGraph 构建的推理-行动循环 Agent，支持工具调用和流式输出。
3. 技能系统：可扩展的技能架构，内置数据分析和文本摘要技能，支持自定义技能注册。
4. MCP 协议集成：标准 MCP 客户端和服务端实现，可以连接外部 MCP Server 扩展能力。
5. A2UI 声明式 UI：Agent 工具调用结果自动生成结构化 UI 卡片，支持表单、信息、列表、确认、图表五种组件类型。

技术栈：后端使用 Python + FastAPI + LangGraph + SQLite + ChromaDB，前端使用 Next.js 15 + React 19 + AI SDK + TypeScript。

预设用户：admin/admin123（租户A管理员），user/user123（租户A普通用户），demo/demo123（租户B管理员）。
""",
    },
    {
        "filename": "快速入门指南.txt",
        "title": "快速入门指南",
        "content": """观心 v2 快速入门指南

第一步：启动系统
运行 scripts/start.sh 脚本，它会自动检查 Python 和 Node.js 环境，创建虚拟环境，安装依赖，启动后端和前端服务。

第二步：登录系统
打开浏览器访问 http://localhost:3000，使用预设账号登录。推荐使用 admin/admin123 登录。

第三步：上传文档
进入知识库页面，上传 txt、md 或 json 文件。系统会自动解析、分块、生成向量嵌入并存储到 ChromaDB。

第四步：AI 对话
进入对话页面，向 AI 提问。AI 会自动检索知识库中的相关内容来回答问题。

第五步：体验技能
在技能市场页面查看已注册的技能。可以执行数据分析技能对数值数组进行统计分析，或使用文本摘要技能提取文本要点。

第六步：A2UI 预览
在 A2UI 预览页面，可以选择不同的组件类型和模板，实时预览 A2UI 卡片的渲染效果。

第七步：MCP 配置
在 MCP 配置页面，可以管理和连接 MCP Server。系统内置了一个天气查询 MCP Server 作为示例。
""",
    },
]

# === 默认 Agent 配置 ===
SEED_AGENT_CONFIGS: List[Dict[str, Any]] = [
    {
        "agent_id": "default",
        "name": "默认助手",
        "description": "观心 v2 默认 AI 助手，具备知识库问答和技能执行能力",
        "model": "gpt-4o-mini",
        "system_prompt": "你是观心 v2 的 AI 助手，可以帮助用户管理知识库、分析数据、回答问题。请友善、专业地回答用户的问题。",
        "temperature": 0.7,
        "max_tokens": 4096,
        "enabled_tools": ["kb_retrieval"],
        "enabled_skills": ["data_analysis", "text_summary"],
        "mcp_servers": ["weather"],
    },
]

# === 默认 MCP Server 配置 ===
SEED_MCP_SERVERS: List[Dict[str, Any]] = [
    {
        "name": "weather",
        "command": sys.executable,
        "args": ["-m", "app.mcp.weather_server"],
        "env": {},
        "description": "天气查询 MCP Server（示例）",
    },
]
