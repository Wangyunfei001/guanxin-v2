# A2UI 测试用例

> 覆盖 5 种组件类型（form_card / info_card / list_card / confirm_card / chart_card）的 Schema 生成、渲染、children 递归、边界情况。

---

## 一、E2E Prompt 测试（用户输入 → 预期 A2UI 卡片）

| # | 用户输入 (Prompt) | 触发工具 | 预期 A2UI 卡片 | 验证点 |
|---|---|---|---|---|
| P1 | "帮我检索知识库里关于部署流程的文档" | `kb_retrieval` | `list_card` | columns: content/filename/score；score 列渲染为彩色 Badge（≥0.8 绿 / ≥0.5 橙 / <0.5 灰） |
| P2 | "执行 test_skill 技能" | `skill_execute` | `info_card` | 若输出含 `chart_data` → `info_card` + 嵌套 `chart_card` children；否则仅 `info_card` |
| P3 | "帮我分析一下最近一周的销售数据趋势" | 任意工具含 `chart_data` 输出 | `info_card` + `chart_card` children | children[0] 为 chart_card, bar/line 图表可正常渲染 |
| P4 | "帮我生成一个用户注册表单" | 触发 form_card 生成的工具 | `form_card` | 所有字段和按钮均为 disabled（展示模式），`type` 为 `input/select/textarea/number/switch` 均正确渲染 |
| P5 | "确认删除这个文档" | 触发 confirm 的工具 | `confirm_card` | danger=true 时 confirm 按钮为 destructive 样式；两个按钮均 disabled |
| P6 | 任意未命中专用模板的工具调用 | 其他工具 | `info_card`（通用降级） | title 为 "工具调用结果：{tool_name}"，content 显示输出 |

---

## 二、ListCard — Score Badge 渲染阈值测试

| # | Score 值 | 预期 Badge 颜色 | 说明 |
|---|---|---|---|
| S1 | `0.95` | 绿色（bg-green-100 text-green-700） | ≥ 0.8 |
| S2 | `0.80` | 绿色 | 边界值 0.8 |
| S3 | `0.79` | 橙色（bg-orange-100 text-orange-700） | < 0.8, ≥ 0.5 |
| S4 | `0.50` | 橙色 | 边界值 0.5 |
| S5 | `0.49` | 灰色（bg-gray-100 text-gray-700） | < 0.5 |
| S6 | `0.02` | 灰色 | 极低分 |

---

## 三、ChartCard — 图表类型渲染测试

| # | `chart_type` | 预期图表组件 | 预期行为 |
|---|---|---|---|
| C1 | `"bar"` | `<BarChart>` | recharts Bar 柱状图，高度 256px（h-64） |
| C2 | `"line"` | `<LineChart>` | recharts Line 折线图，带 dot(r=4) |
| C3 | 未传 chart_type（undefined） | `<BarChart>`（默认 bar） | `props.chart_type \|\| "bar"` 兜底 |
| C4 | `labels.length !== values.length` | 无 crash | `values[idx] ?? 0` 兜底 shorter values |
| C5 | `labels=[]` 且 `values=[]` | 空图表 | ResponsiveContainer 显示空白区域，无 crash |

---

## 四、Children 递归测试

| # | Schema 结构 | 预期渲染 |
|---|---|---|
| R1 | `info_card` + `children: [chart_card]` | InfoCard 下方渲染 ChartCard |
| R2 | `info_card` + `children: [chart_card, list_card]` | InfoCard 下方依次渲染 ChartCard 和 ListCard |
| R3 | `info_card` + `children: [info_card + children: [chart_card]]` | 三层嵌套正确递归 |
| R4 | `info_card` + `children: []` | 不渲染额外子元素，不 crash |
| R5 | `info_card` + 无 children 字段 | 不渲染 children 区域 |

---

## 五、Fallback / 容错测试

| # | 场景 | 预期行为 |
|---|---|---|
| F1 | `component_type: "unknown_card"` | 降级渲染 InfoCard，不 crash |
| F2 | `component_type: ""`（空字符串） | 降级渲染 InfoCard |
| F3 | Schema 缺少 `props` 字段 | 各组件 `props \|\| {}` 兜底，不 crash |
| F4 | Schema props 无 `title` | 显示各组件默认标题（"表单"/"信息"/"列表"/"确认"/"图表"） |
| F5 | FormCard `fields` 为空数组 | 渲染空表单卡片，不 crash |
| F6 | ListCard `rows` 为空数组 | 渲染空表格，不 crash |
| F7 | ListCard `columns` 为空数组 | 渲染空表头，不 crash |
| F8 | ConfirmCard 不传 `danger` | `props.danger \|\| false` → default variant 按钮 |
| F9 | ChartCard 传入无效 `chart_type`（如 `"pie"`） | `chartType \|\| "bar"` → BarChart |

---

## 六、现有 Backend 测试补充建议

> `backend/tests/test_a2ui.py` 已有底子，以下是建议补充的 case。

### 6.1 `TestA2UIRender` 补充

```python
def test_a2ui_render_unknown_component_type_fallback(self, test_client, admin_headers):
    """测试未知 component_type 是否能正常返回（不 500）。"""
    response = test_client.post(
        "/api/a2ui/render-dynamic",
        headers=admin_headers,
        json={
            "component_type": "unknown_card",
            "title": "测试",
            "props": {},
        },
    )
    # 后端应允许任意 component_type 透传，校验由 catalog.validate_schema 负责
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == 0
```

### 6.2 `TestA2UIValidate` 补充

```python
class TestA2UIValidateEdgeCases:
    """Schema 校验边界用例。"""

    def test_empty_children_list(self, test_client, admin_headers):
        """children 为空数组应该合法。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "info_card",
                    "props": {"title": "test"},
                    "children": [],
                }
            },
        )
        data = response.json()
        assert data["data"]["valid"] is True

    def test_nested_three_levels(self, test_client, admin_headers):
        """三层嵌套 children 应递归校验。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "info_card",
                    "props": {},
                    "children": [{
                        "component_type": "info_card",
                        "props": {},
                        "children": [{
                            "component_type": "chart_card",
                            "props": {},
                        }],
                    }],
                }
            },
        )
        data = response.json()
        assert data["data"]["valid"] is True

    def test_nested_invalid_child(self, test_client, admin_headers):
        """嵌套子组件有未知类型应标记为 invalid。"""
        response = test_client.post(
            "/api/a2ui/preview",
            headers=admin_headers,
            json={
                "schema": {
                    "component_type": "info_card",
                    "props": {},
                    "children": [{
                        "component_type": "bad_card",
                        "props": {},
                    }],
                }
            },
        )
        data = response.json()
        assert data["data"]["valid"] is False
```

---

## 七、手工验证 Checklist

打开浏览器 → 登录 → 输入对应 Prompt → 观察：

- [ ] P1: `list_card` 渲染，score 列颜色正确（红黄绿三档）
- [ ] P2: `info_card` 渲染，无 layout 错位
- [ ] P3: `chart_card` 图表渲染，recharts tooltip 可 hover
- [ ] P4: `form_card` 所有字段 disabled，select/switch 正确显示
- [ ] P5: `confirm_card` danger=true 时按钮为红色 destructive
- [ ] 任意外部工具结果：`info_card` 降级渲染
- [ ] 多个 a2ui schema 顺序推入，逐一渲染
- [ ] 快速连续发送消息，a2uiSchemas 数组不串号