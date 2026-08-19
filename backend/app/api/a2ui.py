"""A2UI API 模块。

提供组件目录、模板列表、预览、渲染等接口。
"""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.a2ui.catalog import get_catalog, get_component_spec, validate_schema
from app.a2ui.renderer import render_dynamic, render_for_agent
from app.a2ui.templates import get_templates
from app.core.deps import get_current_user
from app.core.responses import success
from app.models.tenant import User

router = APIRouter(prefix="/a2ui", tags=["A2UI"])


@router.get("/catalog")
async def get_a2ui_catalog(user: User = Depends(get_current_user)):
    """获取 A2UI 组件目录。"""
    return success(get_catalog())


@router.get("/catalog/{component_type}")
async def get_a2ui_component_spec(
    component_type: str,
    user: User = Depends(get_current_user),
):
    """获取指定组件类型的 Schema 规范。"""
    spec = get_component_spec(component_type)
    if spec is None:
        return {"code": 4041, "message": "组件类型未找到", "data": None}
    return success(spec)


@router.get("/templates")
async def get_a2ui_templates(user: User = Depends(get_current_user)):
    """获取所有 A2UI 模板列表。"""
    return success(get_templates())


class PreviewRequest(BaseModel):
    """预览请求。"""

    ui_schema: Dict[str, Any] = Field(alias="schema")


@router.post("/preview")
async def preview_schema(
    request: PreviewRequest,
    user: User = Depends(get_current_user),
):
    """校验并预览 A2UI Schema。"""
    result = validate_schema(request.ui_schema)
    if not result["valid"]:
        return {"code": 4221, "message": "Schema 校验失败", "data": result}
    return success({"valid": True, "schema": request.ui_schema})


class RenderRequest(BaseModel):
    """渲染请求。"""

    template_name: str
    data: Any = None


@router.post("/render")
async def render_template(
    request: RenderRequest,
    user: User = Depends(get_current_user),
):
    """使用预定义模板渲染 A2UI。"""
    schema = render_for_agent(request.template_name, request.data)
    if schema is None:
        return {"code": 4041, "message": "模板未找到或渲染失败", "data": None}
    return success(schema)


class RenderDynamicRequest(BaseModel):
    """动态渲染请求。"""

    component_type: str
    title: str = ""
    props: Dict[str, Any] = {}
    children: Optional[List[Dict[str, Any]]] = None


@router.post("/render-dynamic")
async def render_dynamic_schema(
    request: RenderDynamicRequest,
    user: User = Depends(get_current_user),
):
    """动态构建 A2UI Schema。"""
    schema = render_dynamic(
        component_type=request.component_type,
        title=request.title,
        props=request.props,
        children=request.children,
    )
    return success(schema)
