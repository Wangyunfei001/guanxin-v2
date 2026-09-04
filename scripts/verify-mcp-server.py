#!/usr/bin/env python3
"""Use the official Python MCP SDK to verify the Guanxin stdio gateway."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


EXPECTED_TOOLS = ["knowledge_retrieve", "text_summary", "data_analysis"]


async def main() -> None:
    if not os.environ.get("GUANXIN_API_KEY"):
        raise SystemExit("GUANXIN_API_KEY is required")

    launcher = Path(__file__).resolve().with_name("start-mcp-server.sh")
    params = StdioServerParameters(
        command=str(launcher),
        env=os.environ.copy(),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            initialized = await session.initialize()
            if initialized.serverInfo.version != "0.2.0":
                raise RuntimeError("unexpected Guanxin MCP application version")
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            if names != EXPECTED_TOOLS:
                raise RuntimeError(f"unexpected tools: {names}")

            knowledge = await session.call_tool(
                "knowledge_retrieve", {"query": "ORION-4729", "top_k": 1}
            )
            summary = await session.call_tool(
                "text_summary",
                {
                    "text": "观心提供知识检索。观心支持技能调用。观心遵守租户隔离。",
                    "max_sentences": 2,
                },
            )
            analysis = await session.call_tool(
                "data_analysis", {"data": [1, 2, 3, 4], "analysis_type": "full"}
            )
            results = [knowledge, summary, analysis]
            if any(result.isError for result in results):
                raise RuntimeError("one or more MCP tools returned an error")

            print(f"tools: {', '.join(names)}")
            print(f"knowledge results: {len(knowledge.structuredContent['results'])}")
            print(f"summary keys: {', '.join(summary.structuredContent)}")
            print(f"analysis count: {analysis.structuredContent['count']}")


if __name__ == "__main__":
    asyncio.run(main())
