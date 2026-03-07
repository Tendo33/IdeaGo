# IdeaGo Mentor 文档包

这套文档是按“带教式学习路径”设计的：先建立全局地图，再走一遍真实请求链路，最后进入扩展与高级机制。

## 你会得到什么

- 一条可执行的阅读顺序（不是“随便翻代码”）
- 后端 LangGraph 管道 + 前端 SSE 交互的全链路理解
- 高级特性的设计动机、易错点与调试路径
- 4 周学习计划 + 渐进式练习任务 + 常见问题排查表

## 建议阅读顺序（必须按序）

1. `docs/mentor/00-codebase-map.md`
2. `docs/mentor/01-quickstart-path.md`
3. `docs/mentor/02-request-lifecycle.md`
4. `docs/mentor/03-agent-core.md`
5. `docs/mentor/04-advanced-features.md`
6. `docs/mentor/05-learning-plan.md`
7. `docs/mentor/06-practice-tasks.md`
8. `docs/mentor/07-troubleshooting.md`

## 两条学习路线

- **后端优先（推荐）**：`00 → 01 → 02 → 03 → 04`
- **全栈联动**：`00 → 01 → 02` 后，把 `frontend/src/pages/ReportPage.tsx` 与 `frontend/src/pages/report/useReportLifecycle.ts` 穿插阅读

## 先跑起来（5 分钟）

```bash
uv sync --all-extras
npm --prefix frontend install
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
npm --prefix frontend run dev
```

然后访问：
- 前端：<http://localhost:5173>
- 健康检查：<http://localhost:8000/api/v1/health>

## 这套文档的使用方式

- 每篇文档都有“动手任务”，做完再看下一篇。
- 每次学习尽量只追一个“用户请求”的代码路径，不要并行开太多分支。
- 遇到“看懂了但说不清”的地方，优先回到 `02-request-lifecycle.md` 对照真实调用链。

---

如果你要我继续，我可以在下一步直接给你做一次 **第 1 周 Day 1 的带练任务清单**（按 45~60 分钟切块）。
