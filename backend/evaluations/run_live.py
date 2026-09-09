"""Run with `uv run python -m evaluations.run_live --output <new directory>`.

Uses real configured APIs and production Deep Agents/tools in disposable storage.
No automatic approval, no user data sent, no LangSmith uploads.
"""
import argparse
import asyncio
import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from evaluations.metrics import citation_checks, estimate

CASES = [
    {"id": "knowledge", "prompt": "请检索知识库中的星桥项目验收规范，回答正式交付前需要多少个工作日的验收、谁签字，以及失败后多久复测。引用文件名和原文，未知信息不要猜。", "required": ["5", "2", "项目负责人", "星桥验收规范"], "tools": ["kb_retrieval"]},
    {"id": "research", "prompt": "请使用 web_search 核实 LangGraph 官方文档：持久化需要 checkpointer 吗？thread_id 的作用是什么？interrupt 恢复使用什么命令？用中文分别给出答案，每项紧邻官方来源链接。不要使用非官方转载，不生成文件。", "required": ["checkpointer", "thread_id", "Command"], "tools": ["web_search", "read_source", "record_citation"]},
    {"id": "report", "prompt": "仅根据以下给定资料，写一份简短中文报告，保存为 /reports/acceptance.md。资料A：星桥项目验收期为5个工作日，由项目负责人签字（来源：https://example.com/eval/spec）。资料B：复测在2个工作日内进行（来源：https://example.com/eval/retest）。逐条标明来源，说明这些是用户提供的评估资料而非已联网核实的事实，不增加其他事实。最后告知文件路径。", "required": ["5", "2", "项目负责人"], "tools": ["write_file"]},
    {"id": "approval", "prompt": "请为团队新增一个用户名 eval_member 的普通用户，邮箱 eval_member@example.com。先建立业务审批流程，等待我确认；禁止直接执行或声称用户已经创建。", "required": [], "tools": ["request_business_workflow"]},
]

async def evaluate(args):
    from app.config import settings
    from app.core.sqlite import initialize_database
    from app.core.checkpoints import initialize_checkpointer, close_checkpointer
    from app.models.agent import get_agent_config_store
    from app.models.tenant import User
    from app.services.conversation_store import get_conversation_store
    from app.services.workflow_store import get_workflow_store
    from app.skills.registry import get_skill_registry
    from app.agent.deep_agent import build_deep_agent, checkpoint_config, json_value
    from langchain_core.callbacks import UsageMetadataCallbackHandler

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required; no mock fallback")
    initialize_database()
    await initialize_checkpointer()
    get_skill_registry().register_all()
    config = get_agent_config_store().get_or_create_default("evaluation")
    config.model, config.temperature = args.model, 0
    config.enabled_tools = ["kb_retrieval", "web_search"]
    config.enabled_skills, config.mcp_servers = ["create_user"], []
    get_agent_config_store().save_config(config)
    user = User("eval-user", "eval", "", "evaluation", "Evaluation", "admin")
    kb_error = None
    if args.case in {None, "knowledge"}:
        try:
            from app.services.embedding_service import get_embedding_service
            from app.core.database import get_or_create_collection
            fixture = "星桥验收规范：正式交付前验收期为5个工作日，由项目负责人签字。验收失败后应在2个工作日内复测。"
            vectors, fallback = await asyncio.to_thread(get_embedding_service().embed_texts_with_fallback, [fixture])
            if fallback:
                raise RuntimeError("Real embedding unavailable; random-vector retrieval is not an evaluation")
            get_or_create_collection("evaluation").add(ids=["eval-spec"], documents=[fixture], embeddings=vectors,
                metadatas=[{"doc_id": "eval-spec", "filename": "星桥验收规范.txt"}])
        except Exception as exc:
            kb_error = type(exc).__name__ + ": real embedding unavailable"

    output = Path(args.output)
    results = []
    try:
        for case in CASES:
            if args.case and case["id"] != args.case:
                continue
            started = time.monotonic()
            record = {"case": case["id"], "prompt": case["prompt"], "requested_model": args.model,
                      "started_at": datetime.now(timezone.utc).isoformat(), "test_model": False}
            callback = UsageMetadataCallbackHandler()
            try:
                if case["id"] == "knowledge" and kb_error:
                    raise RuntimeError(kb_error)
                conversation = get_conversation_store().create_conversation("evaluation", "eval-user", "default")
                agent = await build_deep_agent(conversation.conversation_id, user, "quick")
                cfg = checkpoint_config(conversation.conversation_id)
                cfg["callbacks"] = [callback]
                async with asyncio.timeout(240):
                    state = await agent.ainvoke({"messages": [{"role": "user", "content": case["prompt"]}]}, cfg)
                messages = json_value(state.get("messages", []))
                # Store answers/tool evidence/usage, never raw model reasoning.
                record["messages"] = [{k: m[k] for k in ("type", "content", "tool_calls", "name", "usage_metadata") if k in m} for m in messages]
                files = json_value(state.get("files", {}))
                record["files"] = files
                text = "\n".join(m.get("content", "") for m in messages if m.get("type") == "ai" and isinstance(m.get("content"), str))
                if case["id"] == "report":
                    text = files.get("/reports/acceptance.md", {}).get("content", "")
                calls = [t["name"] for m in messages for t in m.get("tool_calls", [])]
                sources, searches = [], []
                for m in messages:
                    if m.get("type") == "tool" and m.get("name") == "web_search":
                        data = json.loads(m["content"])
                        if "error" in data:
                            continue
                        sources.extend(data.get("sources", []))
                        searches.append({k: data.get(k) for k in ("model", "usage", "search_actions")})
                if case["id"] == "report":
                    sources = [{"url": "https://example.com/eval/spec"}, {"url": "https://example.com/eval/retest"}]
                checks = {"required_facts_present": all(s in text for s in case["required"]),
                          "required_tools_called": all(t in calls for t in case["tools"])}
                if case["id"] == "approval":
                    run = get_workflow_store().get_active_for_conversation(conversation.conversation_id, "evaluation", "eval-user")
                    record["workflow"] = run
                    checks["waiting_for_user"] = bool(run and run["status"] in {"waiting_approval", "waiting_input"})
                    checks["no_business_write"] = not Path(settings.user_data_path).exists()
                if case["id"] == "report": checks["file_exists"] = bool(text)
                from app.research.ledger import snapshot
                record["research_review"] = snapshot(conversation.conversation_id)
                if case["id"] == "research":
                    checks["claim_evidence_records"] = len(record["research_review"]["claims"]) >= 3
                    checks["claim_topic_coverage"] = all(any(topic.lower() in c["claim"].lower()
                        for c in record["research_review"]["claims"]) for topic in ("checkpointer", "thread_id", "Command"))
                citations = citation_checks(text, sources)
                if case["id"] in {"research", "report"}:
                    checks["traceable_citations"] = bool(citations["links"]) and not citations["unobserved_links"]
                record.update(status="completed", checks=checks, automated_pass=all(checks.values()),
                    citations=citations, source_evidence=sources, search_usage=searches, answer=text)
            except Exception as exc:
                record.update(status="error", error_type=type(exc).__name__,
                    error=str(exc).replace(settings.openai_api_key, "[redacted]")[:500], automated_pass=False)
            record["elapsed_seconds"] = round(time.monotonic()-started, 3)
            record["model_usage"] = callback.usage_metadata
            record["cost"] = estimate(callback.usage_metadata)
            if record["status"] == "error":
                record["cost"]["complete_model_usage"] = False
            record["search_model_costs"] = []
            for search in record.get("search_usage", []):
                usage = search.get("usage") or {}
                normalized = {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
                    "input_token_details": {"cache_read": usage.get("input_tokens_details", {}).get("cached_tokens")}}
                if normalized["input_tokens"] is not None and normalized["output_tokens"] is not None:
                    record["search_model_costs"].append(estimate({search["model"]: normalized}))
            results.append(record)
            (output / (case["id"] + ".json")).write_text(json.dumps(record, ensure_ascii=False, indent=2))
            print(json.dumps({k: record[k] for k in ("case", "status", "automated_pass", "elapsed_seconds", "model_usage")}, ensure_ascii=False), flush=True)
    finally:
        await close_checkpointer()
    (output / "summary.json").write_text(json.dumps({"cases": results, "manual_review_required": True}, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="deepseek-v4-pro")
    parser.add_argument("--case", choices=[c["id"] for c in CASES])
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="guanxin-live-eval-") as root:
        for setting, name in {"DATABASE_PATH":"app.db", "CHECKPOINT_DATABASE_PATH":"checkpoints.db", "CHROMA_PERSIST_DIR":"chroma", "UPLOAD_DIR":"uploads", "USER_DATA_PATH":"users.json"}.items():
            os.environ[setting] = str(Path(root) / name)
        os.environ["LANGSMITH_TRACING"] = "false"
        asyncio.run(evaluate(args))

if __name__ == "__main__":
    main()
