# 05 · 4 周学习计划（从会用到会改）

> 每周目标：理解 -> 追踪 -> 修改 -> 设计扩展。

## 总目标（4 周后）

你应该能独立完成：
- 增加一个数据源（含后端管道与前端展示联动）
- 改一条 pipeline 逻辑并补测试
- 调试 SSE/状态一致性问题
- 解释主要高级机制的设计取舍

## Week 1：建立主链路直觉

### Day 1-2
- 阅读：`00`、`01`
- 跑通：本地后端 + 前端 + `curl /health`

### Day 3-4
- 阅读：`02`
- 动手：完整跑一次 `analyze -> stream -> report/status`

### Day 5
- 输出：写一页你自己的“请求生命周期笔记”

**周完成标准**
- 不看代码也能讲清 7 个关键阶段。

## Week 2：组件级理解与可替换性

### Day 1-2
- 阅读：`03`
- 重点：`get_orchestrator()` 如何装配对象

### Day 3-4
- 深读：
  - `intent_parser.py`
  - `extractor.py`
  - `aggregator.py`

### Day 5
- 用 `tests/test_llm_layer.py`、`tests/test_sources.py` 验证理解

**周完成标准**
- 你能写出“新增 source 需要改哪些文件”的完整清单。

## Week 3：高级机制与稳定性

### Day 1-2
- 阅读：`04`
- 重点：LLM failover、降级策略、SSE 重连

### Day 3-4
- 追踪：
  - `frontend/src/api/useSSE.ts`
  - `frontend/src/pages/report/useReportLifecycle.ts`

### Day 5
- 做一次“假想故障”推演（端到端）

**周完成标准**
- 你能定位“卡 processing / 结果缺失 / SSE 断流”这三类问题。

## Week 4：实战演练

### Day 1-2
- 从 `06-practice-tasks.md` 做 1~2 个初级任务

### Day 3-4
- 做 1 个中级任务（例如新增事件或字段）

### Day 5
- 做 1 个高级任务（例如 source 扩展 + 前端联动）

**周完成标准**
- 你能提交一组小改动，并说清验证方法与回滚点。

## 每周固定节奏（推荐）

- 周一：读图与架构
- 周二：跟一次真实执行
- 周三：读测试理解边界
- 周四：做一个微改动（即使只是注释/文档）
- 周五：复盘 + 输出笔记

## Definition of Done（学习版）

满足以下 5 条才算“学会一层”：

1. **能口述**：一句话讲清模块职责。
2. **能定位**：30 秒内找到对应文件与函数。
3. **能验证**：给出至少 1 条可执行命令验证理解。
4. **能解释异常**：说出至少 1 个常见失败场景。
5. **能提出改动方案**：最小改动路径 + 风险点。

## 本周就能开始的命令清单

```bash
uv run pytest tests/test_api.py -q
uv run pytest tests/test_langgraph_engine.py -q
uv run pytest tests/test_llm_layer.py -q
npm --prefix frontend run test
```

---

下一篇：`docs/mentor/06-practice-tasks.md`（分层练习题，直接上手）。
