"""Local-only HTTP fixture used by the stdio MCP protocol test."""

from typing import Any

from fastapi import FastAPI, Header, HTTPException


app = FastAPI()


def _authorize(api_key: str | None) -> None:
    if api_key != "protocol-test-key":
        raise HTTPException(status_code=401, detail="invalid key")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/knowledge/retrieve")
async def retrieve(
    payload: dict[str, Any],
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(x_api_key)
    return {
        "code": 0,
        "message": "success",
        "data": [
            {
                "chunk_id": "chunk-1",
                "content": f"result:{payload['query']}",
                "score": 0.9,
                "doc_id": "doc-1",
                "filename": "demo.txt",
                "metadata": {},
            }
        ],
    }


@app.post("/api/skills/execute")
async def execute_skill(
    payload: dict[str, Any],
    x_api_key: str | None = Header(default=None),
) -> dict[str, Any]:
    _authorize(x_api_key)
    skill_name = payload["skill_name"]
    params = payload["params"]
    if skill_name == "text_summary":
        output: Any = {"summary": params["text"], "keywords": ["demo"]}
    elif skill_name == "data_analysis":
        output = {"count": len(params["data"]), "mean": 2.0}
    else:
        return {"code": 4041, "message": "skill not found", "data": None}
    return {
        "code": 0,
        "message": "success",
        "data": {"success": True, "output": output, "error": "", "metadata": {}},
    }
