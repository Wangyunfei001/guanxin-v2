from evaluations.metrics import citation_checks, estimate


def test_cost_unknown_is_not_zero_and_cache_discount_is_counted():
    assert estimate({})["complete_model_usage"] is False
    assert estimate({"unknown": {}})["unknown_models"] == ["unknown"]
    usage = {"input_tokens": 1_000_000, "output_tokens": 0, "input_token_details": {"cache_read": 1_000_000}}
    assert estimate({"deepseek-v4-pro": usage})["known_model_usd_interval"] == [0.022, 0.044]
    assert not estimate({"deepseek-v4-pro": {"input_tokens": 1, "output_tokens": 1}})["complete_model_usage"]


def test_observed_url_is_not_automatic_entailment():
    result = citation_checks('[A](https://example.com/a) [B](https://example.com/b)', [{"url": "https://example.com/a"}])
    assert result["unobserved_links"] == ["https://example.com/b"]
    assert result["entailment"] == "requires_human_review"


def test_legacy_resume_migrates_once_and_preserves_archive(test_client, admin_headers, user_headers, monkeypatch):
    from tests.test_langchain import new_thread
    from app.services.research_store import get_research_store
    from app.api import research
    from app.services import agent_run_store as runs
    cid = new_thread(test_client, admin_headers)
    store = get_research_store()
    run = store.create_run(tenant_id="tenant-a", user_id="admin-001", conversation_id=cid, mode="quick", goal="核实历史资料", budget={})
    store.set_status(run["run_id"], "interrupted", report="历史报告原文")
    launched = []
    monkeypatch.setattr(research, "launch_run", lambda *args: launched.append(args))
    url = f'/api/agent/research/{run["run_id"]}/resume'
    assert test_client.post(url, headers=user_headers).status_code == 404
    assert test_client.post(url, headers=admin_headers).status_code == 200
    assert test_client.post(url, headers=admin_headers).status_code == 200
    assert len(launched) == 1
    assert "历史报告原文" in launched[0][2]["content"]
    assert launched[0][1].user_id == "admin-001"
    saved = store.get_run(run["run_id"])
    assert saved["report"] == "历史报告原文" and saved["status"] == "cancelled"
    runs.finish_run(launched[0][0], "completed")


def test_legacy_resume_respects_active_native_run(test_client, admin_headers):
    from tests.test_langchain import new_thread
    from app.services.research_store import get_research_store
    from app.services import agent_run_store as runs
    cid = new_thread(test_client, admin_headers)
    store = get_research_store()
    old = store.create_run(tenant_id="tenant-a", user_id="admin-001", conversation_id=cid, mode="quick", goal="核实历史资料", budget={})
    store.set_status(old["run_id"], "interrupted")
    native, _ = runs.admit_run(cid, "busy")
    assert test_client.post(f'/api/agent/research/{old["run_id"]}/resume', headers=admin_headers).status_code == 409
    assert store.get_run(old["run_id"])["status"] == "interrupted"
    runs.finish_run(native, "completed")
