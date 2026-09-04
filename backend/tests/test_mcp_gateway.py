"""Tests for the authenticated Guanxin stdio MCP gateway."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from app.mcp.gateway_server import (
    GatewayConfig,
    GatewayError,
    GuanxinApiClient,
)


API_KEY = "gateway-secret-key"


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> GuanxinApiClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return GuanxinApiClient(
        GatewayConfig(api_base_url="http://guanxin.test/api", api_key=API_KEY),
        client=http,
    )


def _success(data: Any) -> httpx.Response:
    return httpx.Response(200, json={"code": 0, "message": "success", "data": data})


def test_gateway_config_requires_api_key() -> None:
    with pytest.raises(GatewayError, match="GUANXIN_API_KEY"):
        GatewayConfig.from_env({})

    config = GatewayConfig.from_env(
        {"GUANXIN_API_KEY": " key ", "GUANXIN_API_BASE_URL": "http://api.test/api/"}
    )
    assert config.api_key == "key"
    assert config.api_base_url == "http://api.test/api"


@pytest.mark.asyncio
async def test_knowledge_retrieve_forwards_api_key_and_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://guanxin.test/api/knowledge/retrieve"
        assert request.headers["X-API-Key"] == API_KEY
        assert json.loads(request.content) == {"query": "观心", "top_k": 3}
        return _success([{"content": "命中"}])

    api = _client(handler)
    assert await api.knowledge_retrieve(" 观心 ", 3) == [{"content": "命中"}]
    await api._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "arguments", "skill_name"),
    [
        ("text_summary", ("一段文本", 2), "text_summary"),
        ("data_analysis", ([1, 2, 3], "full"), "data_analysis"),
    ],
)
async def test_read_only_skills_are_fixed(
    method: str,
    arguments: tuple[Any, ...],
    skill_name: str,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["skill_name"] == skill_name
        return _success({"success": True, "output": {"skill": skill_name}})

    api = _client(handler)
    result = await getattr(api, method)(*arguments)
    assert result == {"skill": skill_name}
    await api._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method", "arguments", "message"),
    [
        ("knowledge_retrieve", ("", 5), "query"),
        ("knowledge_retrieve", ("query", 0), "top_k"),
        ("text_summary", ("", 3), "text"),
        ("text_summary", ("text", 0), "max_sentences"),
        ("data_analysis", ([], "basic"), "data"),
        ("data_analysis", ([1, "bad"], "basic"), "数值"),
        ("data_analysis", ([1], "unknown"), "analysis_type"),
    ],
)
async def test_gateway_validates_arguments(
    method: str,
    arguments: tuple[Any, ...],
    message: str,
) -> None:
    api = _client(lambda _: _success(None))
    with pytest.raises(GatewayError, match=message):
        await getattr(api, method)(*arguments)
    await api._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "message"),
    [(401, "认证失败"), (403, "无权"), (500, "HTTP 500")],
)
async def test_gateway_maps_http_errors(status: int, message: str) -> None:
    api = _client(lambda _: httpx.Response(status, text=f"never expose {API_KEY}"))
    with pytest.raises(GatewayError, match=message) as captured:
        await api.knowledge_retrieve("query")
    assert API_KEY not in str(captured.value)
    await api._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_gateway_maps_business_and_skill_errors_without_leaking_key() -> None:
    responses = iter(
        [
            httpx.Response(
                200,
                json={"code": 4001, "message": f"bad {API_KEY}", "data": None},
            ),
            _success({"success": False, "error": f"skill bad {API_KEY}"}),
        ]
    )
    api = _client(lambda _: next(responses))
    with pytest.raises(GatewayError) as business:
        await api.knowledge_retrieve("query")
    with pytest.raises(GatewayError) as skill:
        await api.text_summary("text")
    assert API_KEY not in str(business.value)
    assert API_KEY not in str(skill.value)
    assert "[REDACTED]" in str(business.value)
    assert "[REDACTED]" in str(skill.value)
    await api._client.aclose()  # type: ignore[union-attr]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("exception", "message"),
    [
        (httpx.ReadTimeout("slow"), "请求超时"),
        (httpx.ConnectError("offline"), "无法连接"),
    ],
)
async def test_gateway_maps_network_errors(exception: Exception, message: str) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise exception

    api = _client(handler)
    with pytest.raises(GatewayError, match=message):
        await api.knowledge_retrieve("query")
    await api._client.aclose()  # type: ignore[union-attr]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_api(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(f"fake API exited early: {process.stderr.read()}")
        try:
            if httpx.get(f"{base_url}/health", timeout=0.25).status_code == 200:
                return
        except httpx.RequestError:
            time.sleep(0.05)
    raise AssertionError("fake API did not become ready")


@pytest.mark.asyncio
@pytest.mark.parametrize("use_launcher", [False, True])
async def test_stdio_protocol_lists_and_calls_all_tools(use_launcher: bool) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    fake_api = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "tests.mcp_fake_api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=os.path.dirname(os.path.dirname(__file__)),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_api(base_url, fake_api)
        env = os.environ.copy()
        env.update(
            {
                "GUANXIN_API_BASE_URL": f"{base_url}/api",
                "GUANXIN_API_KEY": "protocol-test-key",
            }
        )
        params = StdioServerParameters(
            command=(
                str(Path(__file__).resolve().parents[2] / "scripts/start-mcp-server.sh")
                if use_launcher else sys.executable
            ),
            args=[sys.executable] if use_launcher else ["-m", "app.mcp.gateway_server"],
            env=env,
        )
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                listed = await session.list_tools()
                assert [tool.name for tool in listed.tools] == [
                    "knowledge_retrieve",
                    "text_summary",
                    "data_analysis",
                ]

                knowledge = await session.call_tool(
                    "knowledge_retrieve", {"query": "观心", "top_k": 1}
                )
                summary = await session.call_tool(
                    "text_summary", {"text": "测试文本", "max_sentences": 2}
                )
                analysis = await session.call_tool(
                    "data_analysis", {"data": [1, 2, 3], "analysis_type": "full"}
                )

                assert not knowledge.isError
                assert not summary.isError
                assert not analysis.isError
                assert knowledge.structuredContent == {
                    "results": [
                        {
                            "chunk_id": "chunk-1",
                            "content": "result:观心",
                            "score": 0.9,
                            "doc_id": "doc-1",
                            "filename": "demo.txt",
                            "metadata": {},
                        }
                    ]
                }
                assert summary.structuredContent == {
                    "summary": "测试文本",
                    "keywords": ["demo"],
                }
                assert analysis.structuredContent == {"count": 3, "mean": 2.0}
    finally:
        fake_api.terminate()
        try:
            fake_api.wait(timeout=5)
        except subprocess.TimeoutExpired:
            fake_api.kill()
            fake_api.wait(timeout=5)
