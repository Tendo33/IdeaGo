# IdeaGo Mentor 文档包

这套文档是给“准备真正接手 IdeaGo 的开发者”写的，不是泛泛介绍项目，而是按当前代码结构带你建立一条可复用的阅读路径。

## 这套文档解决什么问题

- 帮你先建立当前仓库的真实地图，而不是沿着旧目录名瞎找
- 帮你把“登录后发起分析 -> 后端执行 -> SSE 推送 -> 报告落库 -> 前端展示”这条主链路讲清楚
- 帮你理解项目近阶段新增的关键能力：认证、配额、通知、双缓存实现、SSE 恢复
- 帮你把学习从“看懂”推进到“敢改、会验、知道风险”

## 阅读前先知道 3 件事

1. 项目规范优先读 `ai_docs/`，不是旧的 `doc/`
2. 前端现在是 `frontend/src/features/*` 结构，不再是 `frontend/src/pages/*`
3. `POST /api/v1/analyze`、`/reports/*`、SSE 流都需要认证，学习主链路时默认你已经完成登录

## 建议阅读顺序

1. `docs/mentor/00-codebase-map.md`
2. `docs/mentor/01-quickstart-path.md`
3. `docs/mentor/02-request-lifecycle.md`
4. `docs/mentor/03-agent-core.md`
5. `docs/mentor/04-advanced-features.md`
6. `docs/mentor/05-learning-plan.md`
7. `docs/mentor/06-practice-tasks.md`
8. `docs/mentor/07-troubleshooting.md`

## 两条学习路线

- 后端优先：`00 -> 01 -> 02 -> 03 -> 04`
- 全栈联动：`00 -> 01 -> 02` 之后，把 `frontend/src/features/reports/ReportPage.tsx`、`frontend/src/features/reports/components/useReportLifecycle.ts`、`frontend/src/lib/api/useSSE.ts` 穿插阅读

## 先跑起来

```bash
uv sync --all-extras
pnpm --prefix frontend install
uv run uvicorn ideago.api.app:create_app --factory --reload --port 8000
pnpm --prefix frontend dev
```

然后访问：

- 前端：<http://localhost:5173>
- 公开健康检查：<http://localhost:8000/api/v1/health>

## 这套文档怎么用

- 每篇文档都带“动手任务”，建议做完再进入下一篇
- 每次只跟一条真实链路，不要同时开太多阅读分支
- 看到路径不一致时，以当前仓库结构和 `ai_docs/` 为准
- 如果你“能看懂但说不清”，先回到 `02-request-lifecycle.md`，重新沿真实调用链走一遍

## 最适合的使用场景

- 新加入项目，需要在 1 到 2 天内摸清主流程
- 准备接手报告页、SSE、pipeline、source 扩展等模块
- 已经做过一些改造，现在想把理解重新校正到当前代码版本
