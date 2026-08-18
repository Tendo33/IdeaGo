# 产品能力增量

## 已完成

### 1. `force_refresh`（体检 #30）

缓存命中会短路整条流水线，所以用户想要「最新证据」此前**只能靠改措辞**
把 cache_key 撞开——这是一个人人都会遇到、但没有正式入口的需求。

贯穿链路：`AnalyzeRequest.force_refresh` → 路由 → `_run_pipeline` →
`LangGraphEngine.run(force_refresh=)` → `GraphState["force_refresh"]` →
`cache_lookup_node` 提前返回 `is_cache_hit: False`（**连缓存都不查**）。

配额照常扣：流水线真的在跑。这一点与 C2 的「缓存命中退配额」是自洽的——
付费与否只取决于是否真的产生了 LLM 成本。

前端 `startAnalysis(query, { forceRefresh })` 已就绪；UI 入口未加
（属于产品决策，留给设计，接口先备好）。

### 2. 配额告警幂等

原来只要使用率越过阈值，**之后每一次分析都会发一封邮件**——越接近上限
骚扰越密集。改为每用户每 UTC 日最多一封。

刻意保持进程内：配额本身按日重置，漏发一封告警的代价很低，为此建一张表
不成比例。带上限与按日淘汰，内存有界。

## 未做：PDF / 分享链接导出

体检把它和 `force_refresh` 列在同一项。本轮**未做**，理由：

- PDF 需要引入渲染依赖（headless 浏览器或 reportlab 之类），
  与父任务「不引入新框架」的约束直接冲突
- 分享链接需要一套新的、无需登录即可读取的授权模型（带过期的只读 token），
  那是一个独立的安全设计，不该塞在收尾子任务里顺手做
- 现有 Markdown 导出已经覆盖「把报告拿出去」的基本诉求

两项都记入体检报告的「未做」清单。

## 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run mypy src                            → Success: no issues found in 90 source files
uv run pytest                              → 891 passed, 0 failed, 覆盖率 84.86%
pnpm --prefix frontend lint / typecheck    → 通过
pnpm --prefix frontend test                → 38 files / 247 tests passed
pnpm --prefix frontend build               → OK
```

新增 `tests/test_product_increments.py` 10 个 + 集成测试 2 个
（`force_refresh` 必须一路传到 orchestrator；默认不传时必须为 false）。

### 端到端测试在这里立刻兑现了价值

给 `orchestrator.run()` 加 `force_refresh` 参数后，**5 个集成测试当场变红**——
因为假 orchestrator 的签名没跟上。这正是 E1 那套测试要抓的东西：
跨层签名变更在单层 mock 的测试里是看不见的。

## 既有测试的行为变更

| 测试 | 变更 |
|---|---|
| `client.test.ts` `sends POST with query...` | 请求体现在含 `force_refresh: false`；另加一个用例钉住显式 opt-in 的路径 |
| `ReportPage.test.tsx` ×2 | `useCreateAnalysis` 现在总是传选项对象，第二个实参由 `undefined` 变为 `{}` |
