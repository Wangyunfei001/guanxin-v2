"""Confirmation metadata shared by Agent and protocol adapters."""

from copy import deepcopy


CONFIRM_FORM_FIELDS: dict[str, dict] = {
    "single_create": {
        "title": "创建新用户",
        "fields": [
            {"name": "username", "label": "用户名", "type": "text", "required": True, "placeholder": "请输入用户名"},
            {"name": "email", "label": "邮箱", "type": "email", "required": True, "placeholder": "请输入邮箱地址"},
            {"name": "role", "label": "角色", "type": "select", "required": False, "options": ["admin", "user", "viewer"], "default": "user"},
        ],
    },
    "single_update": {
        "title": "更新用户信息",
        "fields": [
            {"name": "user_id", "label": "用户ID", "type": "text", "required": True, "placeholder": "请输入用户ID"},
            {"name": "username", "label": "新用户名", "type": "text", "required": False, "placeholder": "留空则不修改"},
            {"name": "email", "label": "新邮箱", "type": "email", "required": False, "placeholder": "留空则不修改"},
            {"name": "role", "label": "新角色", "type": "select", "required": False, "options": ["admin", "user", "viewer"]},
        ],
    },
    "single_delete": {
        "title": "删除用户",
        "fields": [
            {"name": "user_id", "label": "用户ID", "type": "text", "required": True, "placeholder": "请输入要删除的用户ID"},
        ],
        "danger": True,
    },
    "batch_operation": {
        "title": "导出数据",
        "fields": [
            {"name": "data_type", "label": "数据类型", "type": "select", "required": True, "options": ["users", "logs", "reports"]},
            {"name": "format", "label": "导出格式", "type": "select", "required": False, "options": ["csv", "json", "xlsx"], "default": "csv"},
            {"name": "date_range", "label": "日期范围", "type": "text", "required": False, "placeholder": "如: 2024-01-01~2024-12-31"},
        ],
    },
}


def get_confirmation_entities(intent_label: str) -> dict:
    return deepcopy(CONFIRM_FORM_FIELDS.get(intent_label, {}))
