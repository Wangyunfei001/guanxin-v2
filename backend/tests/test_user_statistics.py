"""Query statistics describe the filtered set, not the displayed page."""
from app.models.skill_context import SkillContext
from app.services import user_store
from app.skills.builtins.query_users import QueryUsersSkill

CONTEXT = SkillContext(tenant_id="tenant-a", user_id="usr_1", user_role="admin", conversation_id="cid_1")


def test_statistics_cover_filtered_users_before_pagination(monkeypatch):
    monkeypatch.setattr(user_store, "_load", lambda: [
        {"username": "Alice", "email": "a@example.com", "role": "admin", "status": "active"},
        {"username": "Alan", "email": "b@example.com", "role": "user", "status": "inactive"},
        {"username": "Bob", "email": "c@example.com", "role": "user", "status": "active"},
    ])
    result = user_store.query_users(keyword="al", page_size=1)
    assert len(result["users"]) == 1
    assert result["statistics"] == {"total": 2, "roles": {"admin": 1, "user": 1}, "statuses": {"active": 1, "inactive": 1}}
    assert result["filters"] == {"keyword": "al", "role": ""}
    assert user_store.query_users(role="user", page=3, page_size=1)["statistics"]["total"] == 2
    assert user_store.query_users(keyword="nobody")["statistics"] == {"total": 0, "roles": {}, "statuses": {}}


async def test_skill_output_normalizes_unset_filters(monkeypatch):
    """The tool payload is what the dashboard parses, so assert its exact shape."""
    monkeypatch.setattr(user_store, "_load", lambda: [
        {"user_id": "usr_1", "username": "Alice", "email": "a@example.com", "role": "admin", "status": "active"},
        {"user_id": "usr_2", "username": "Bob", "email": "b@example.com", "role": "user", "status": "inactive"},
    ])
    skill = QueryUsersSkill()
    # Optional arguments reach the skill as None when the model omits them.
    result = await skill.execute({"keyword": None, "role": None, "page": None, "page_size": None}, CONTEXT)
    payload = result.to_dict()
    assert payload["success"] is True
    output = payload["output"]
    assert output["total"] == 2
    assert output["page"] == 1 and output["page_size"] == 10
    assert output["filters"] == {"keyword": "", "role": ""}
    assert output["statistics"] == {"total": 2, "roles": {"admin": 1, "user": 1}, "statuses": {"active": 1, "inactive": 1}}
    # The chart is derived from the same full filtered set, not from the current page.
    assert output["chart_data"]["labels"] == ["admin", "user"]
    assert output["chart_data"]["values"] == [1, 1]


async def test_skill_output_keeps_applied_filters(monkeypatch):
    monkeypatch.setattr(user_store, "_load", lambda: [
        {"user_id": "usr_1", "username": "Alice", "email": "a@example.com", "role": "admin", "status": "active"},
        {"user_id": "usr_2", "username": "Bob", "email": "b@example.com", "role": "user", "status": "inactive"},
    ])
    skill = QueryUsersSkill()
    result = await skill.execute({"keyword": "ali", "role": "admin", "page": 1, "page_size": 10}, CONTEXT)
    output = result.to_dict()["output"]
    assert output["filters"] == {"keyword": "ali", "role": "admin"}
    assert output["total"] == 1
    assert output["statistics"] == {"total": 1, "roles": {"admin": 1}, "statuses": {"active": 1}}


async def test_create_user_chart_counts_every_user_not_only_one_page(monkeypatch):
    """The chart used to count the first page only, so 12 users reported 10."""
    monkeypatch.setattr(user_store, "_load", lambda: [
        {"user_id": f"usr_{index}", "username": f"User{index}", "email": f"u{index}@example.com",
         "role": "admin" if index < 3 else "user", "status": "active"}
        for index in range(12)
    ])
    from app.skills.builtins.create_user import CreateUserSkill
    skill = CreateUserSkill()
    result = await skill.execute({"username": "New One", "email": "new@example.com", "role": "user"}, CONTEXT)
    output = result.to_dict()["output"]
    assert output["chart_data"]["labels"] == ["admin", "user"]
    assert sum(output["chart_data"]["values"]) == 12
