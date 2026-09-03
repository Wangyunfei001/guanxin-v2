"""Tenant-aware stdio MCP gateway for Guanxin's read-only HTTP APIs."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import httpx


DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api"
REQUEST_TIMEOUT = httpx.Timeout(30.0, connect=5.0)


class GatewayError(RuntimeError):
    """A sanitized error that is safe to return to an MCP client."""


@dataclass(frozen=True)
class GatewayConfig:
    api_base_url: str
    api_key: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "GatewayConfig":
        values = environ if environ is not None else os.environ
        api_key = values.get("GUANXIN_API_KEY", "").strip()
        if not api_key:
            raise GatewayError("缺少必填环境变量 GUANXIN_API_KEY")
        base_url = values.get("GUANXIN_API_BASE_URL", DEFAULT_API_BASE_URL).strip()
        if not base_url:
            base_url = DEFAULT_API_BASE_URL
        return cls(api_base_url=base_url.rstrip("/"), api_key=api_key)


class GuanxinApiClient:
    """Small authenticated adapter around Guanxin's existing REST API."""

    def __init__(
        self,
        config: GatewayConfig,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.config = config
        self._client = client

    def _sanitize(self, message: str) -> str:
        return message.replace(self.config.api_key, "[REDACTED]")

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        headers = {"X-API-Key": self.config.api_key}
        url = f"{self.config.api_base_url}/{path.lstrip('/')}"

        try:
            if self._client is not None:
                response = await self._client.post(url, json=payload, headers=headers)
            else:
                async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                    response = await client.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise GatewayError("观心 API 请求超时，请稍后重试") from exc
        except httpx.RequestError as exc:
            raise GatewayError("无法连接观心 API，请确认后端服务已启动") from exc

        if response.status_code == 401:
            raise GatewayError("观心 API 认证失败，请检查 GUANXIN_API_KEY")
        if response.status_code == 403:
            raise GatewayError("当前 API Key 无权执行此工具")
        if response.status_code < 200 or response.status_code >= 300:
            raise GatewayError(f"观心 API 返回 HTTP {response.status_code}")

        try:
            body = response.json()
        except ValueError as exc:
            raise GatewayError("观心 API 返回了无法解析的响应") from exc
        if not isinstance(body, dict):
            raise GatewayError("观心 API 返回了无效响应")
        if body.get("code") != 0:
            message = body.get("message")
            safe_message = message if isinstance(message, str) and message else "未知业务错误"
            safe_message = self._sanitize(safe_message)
            raise GatewayError(f"观心 API 调用失败：{safe_message}")
        return body.get("data")

    async def knowledge_retrieve(self, query: str, top_k: int = 5) -> Any:
        normalized = query.strip() if isinstance(query, str) else ""
        if not normalized:
            raise GatewayError("query 不能为空")
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            raise GatewayError("top_k 必须是 1 到 20 的整数")
        return await self._post(
            "/knowledge/retrieve",
            {"query": normalized, "top_k": top_k},
        )

    async def text_summary(self, text: str, max_sentences: int = 3) -> Any:
        normalized = text.strip() if isinstance(text, str) else ""
        if not normalized:
            raise GatewayError("text 不能为空")
        if (
            isinstance(max_sentences, bool)
            or not isinstance(max_sentences, int)
            or not 1 <= max_sentences <= 20
        ):
            raise GatewayError("max_sentences 必须是 1 到 20 的整数")
        return await self._execute_skill(
            "text_summary",
            {"text": normalized, "max_sentences": max_sentences},
        )

    async def data_analysis(
        self,
        data: Sequence[float],
        analysis_type: str = "basic",
    ) -> Any:
        if isinstance(data, (str, bytes)) or not isinstance(data, Sequence) or not data:
            raise GatewayError("data 必须是非空数值数组")
        normalized: list[float] = []
        for value in data:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise GatewayError("data 必须只包含数值")
            normalized.append(value)
        if analysis_type not in {"basic", "full"}:
            raise GatewayError("analysis_type 仅支持 basic 或 full")
        return await self._execute_skill(
            "data_analysis",
            {"data": normalized, "analysis_type": analysis_type},
        )

    async def _execute_skill(self, skill_name: str, params: dict[str, Any]) -> Any:
        result = await self._post(
            "/skills/execute",
            {"skill_name": skill_name, "params": params},
        )
        if not isinstance(result, dict):
            raise GatewayError("Skill 返回了无效响应")
        if not result.get("success"):
            message = result.get("error")
            safe_message = message if isinstance(message, str) and message else "未知错误"
            safe_message = self._sanitize(safe_message)
            raise GatewayError(f"Skill 执行失败：{safe_message}")
        return result.get("output")


def create_server(api: GuanxinApiClient):
    """Build the MCP server around a configured API adapter."""
    from mcp.server import Server
    from mcp.types import Tool, ToolAnnotations

    server = Server("guanxin-v2-gateway")
    read_only = ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="knowledge_retrieve",
                description="检索当前 API Key 所属租户的观心知识库。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "minLength": 1},
                        "top_k": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 5,
                        },
                    },
                    "required": ["query"],
                },
                annotations=read_only,
            ),
            Tool(
                name="text_summary",
                description="使用观心的只读文本摘要 Skill。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "minLength": 1},
                        "max_sentences": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 20,
                            "default": 3,
                        },
                    },
                    "required": ["text"],
                },
                annotations=read_only,
            ),
            Tool(
                name="data_analysis",
                description="使用观心的数据分析 Skill 统计数值数组。",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "data": {
                            "type": "array",
                            "minItems": 1,
                            "items": {"type": "number"},
                        },
                        "analysis_type": {
                            "type": "string",
                            "enum": ["basic", "full"],
                            "default": "basic",
                        },
                    },
                    "required": ["data"],
                },
                annotations=read_only,
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> Any:
        if name == "knowledge_retrieve":
            return {
                "results": await api.knowledge_retrieve(
                    arguments.get("query", ""), arguments.get("top_k", 5)
                )
            }
        if name == "text_summary":
            result = await api.text_summary(
                arguments.get("text", ""), arguments.get("max_sentences", 3)
            )
            return result if isinstance(result, dict) else {"result": result}
        if name == "data_analysis":
            result = await api.data_analysis(
                arguments.get("data", []), arguments.get("analysis_type", "basic")
            )
            return result if isinstance(result, dict) else {"result": result}
        raise GatewayError(f"未知工具：{name}")

    return server


async def run_stdio(config: GatewayConfig) -> None:
    """Run the gateway over stdin/stdout."""
    from mcp.server.stdio import stdio_server

    server = create_server(GuanxinApiClient(config))
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    try:
        config = GatewayConfig.from_env()
    except GatewayError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(2) from None
    asyncio.run(run_stdio(config))


if __name__ == "__main__":
    main()
