# 端到端与契约测试

## Goal

补上项目此前完全没有的跨层测试：`POST /analyze → SSE 终态 → GET /reports/{id} 可读`。

## 为什么这条链路必须有测试

体检发现前端 `useReportStatusResolution.ts` 有 459 行、三个互相递归的
reconcile 解析器，每个带 3 次指数退避重试——全部是为了回答一个问题：
「SSE 说 ready 了，报告到底能不能读了？」

那是**补偿性复杂度**：后端 `REPORT_READY` 与状态行写入之间存在可观测窗口，
前端只能靠重试兜住。C2 修了后端顺序，但**没有任何测试守住这个契约**——
下次有人调换两行代码，前端又会开始随机失败，而且没人知道为什么。

所有既有测试都是单层 mock 的。这条链路一个测试都没有。

## 已完成

`tests/integration/test_analyze_flow.py` 12 个用例，用**真实 FastAPI 应用 +
真实 FileCache + 假 orchestrator** 驱动，所以路由、中间件、归属校验、
SSE 分帧、状态流转是一起被验证的：

| 用例 | 守住的契约 |
|---|---|
| `test_analyze_to_readable_report` | **核心**：状态说 complete 之后，`GET /reports/{id}` 必须立刻可读。断言消息里直接写明「这正是前端 reconcile 循环当初要兜的竞态」 |
| `test_sse_stream_replays_history_and_ends_on_terminal_event` | 重连时历史被回放，且流以终态事件结束 |
| `test_failed_run_surfaces_as_failed_status_not_a_hang` | 失败会变成 `failed` + `PIPELINE_FAILURE`，不是永远 processing |
| `test_another_user_cannot_reach_the_report` | 归属在 detail / export / delete / stream **四条路径**上都生效，且失败尝试不影响属主 |
| `test_export_returns_markdown_for_the_owner` | 导出返回 markdown 且含报告标题 |
| `test_status_endpoint_reports_not_found_for_unknown_report` | 未知报告返回 `not_found` 而非 5xx |
| `TestMiddlewareContract` ×5 | CSRF 拦截、短路响应仍带 CORS 与 trace 头、未认证拒绝、安全响应头、trace id 回显 |
| `test_report_detail_payload_matches_the_frontend_contract` | 报告详情字段集合不漂移（跨层契约，漂移会静默打断 SPA） |

CI 的 backend job 增加一个独立的 `Integration suite` step，让跨层失败一眼可见，
而不是淹没在完整 run 的输出里。

## 过程记录

`_FakeOrchestrator` 一开始用 `ResearchReport(id=..., query=...)` 构造，
连续踩到三层必填字段（`intent` → `target_scenario` → `keywords_en`…）。
与其逐个猜，改为参照 `tests/test_api.py::_make_test_report` 的既有写法抽出
`_build_report()`。这也顺带说明：报告模型的必填面很宽，跨层测试比逐字段
mock 更能反映真实调用。

## 验证证据

```
uv run pytest tests/integration -q         → 12 passed
uv run ruff check src tests scripts        → All checks passed!
uv run mypy src                            → Success: no issues found in 89 source files
uv run pytest                              → 868 passed, 0 failed, 覆盖率 84.77%
```

## 交给后续

现在有了这张安全网，`useReportStatusResolution.ts` 的三层递归 reconcile
可以安全简化了（D1 里明确推迟到此时）。建议做法：
先让集成测试覆盖「SSE ready 后立即读取」的前端等价路径，再逐层删除重试。
本轮不做——它是重构而非修复，且属于体检报告 🌱 长期基建那一档。
