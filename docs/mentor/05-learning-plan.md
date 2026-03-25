# 05 · 4 周学习计划

> 目标不是“读完文档”，而是 4 周后你已经具备独立改动这套系统的能力。

## 4 周后的目标

你应该能独立完成：

- 定位并解释一条真实分析请求的全链路
- 修改一个 pipeline 节点并补上验证
- 排查 SSE、状态恢复、权限隔离中的常见问题
- 做一个小型跨端改动，例如新增报告字段或新进度事件

## Week 1：建立主链路

### Day 1

- 阅读：`00`、`01`
- 任务：跑起前后端，验证 `/api/v1/health`

### Day 2-3

- 阅读：`02`
- 任务：沿着 `HomePage -> /analyze -> _run_pipeline -> /stream -> /reports/:id` 走一遍

### Day 4-5

- 输出：写一份你自己的生命周期笔记
- 建议至少包含：
  - 入口文件
  - 中间状态
  - 终态
  - 失败路径

本周完成标准：

- 你不看代码也能讲清楚“一个分析请求如何走到报告页”

## Week 2：理解核心组件与替换点

### Day 1-2

- 阅读：`03`
- 深入：
  - `src/ideago/api/dependencies.py`
  - `src/ideago/cache/base.py`
  - `src/ideago/contracts/protocols.py`

### Day 3-4

- 深读：
  - `intent_parser.py`
  - `extractor.py`
  - `aggregator.py`

### Day 5

- 跑测试：

```bash
uv run pytest tests/test_llm_layer.py -q
uv run pytest tests/test_sources.py -q
uv run pytest tests/test_langgraph_engine.py -q
```

本周完成标准：

- 你能写出“新增一个 source 至少要改哪些文件”

## Week 3：稳定性与高级机制

### Day 1-2

- 阅读：`04`
- 重点理解：
  - LLM retry / failover
  - extraction degrade
  - SSE 历史重放与重连

### Day 3-4

- 前端重点跟读：
  - `frontend/src/lib/api/useSSE.ts`
  - `frontend/src/features/reports/components/useReportLifecycle.ts`

### Day 5

- 做一次“故障故事线”推演

本周完成标准：

- 你能定位至少三类问题：
  - 一直 processing
  - SSE 断流后页面不恢复
  - 报告 ready 但内容拿不到

## Week 4：开始动手改

### Day 1-2

- 从 `06-practice-tasks.md` 里选 1 到 2 个低风险任务

### Day 3-4

- 做 1 个中等复杂度任务
- 要求带验证命令和风险说明

### Day 5

- 回顾：
  - 你改了哪些层
  - 哪些层最容易遗漏
  - 哪些测试最值得优先跑

本周完成标准：

- 你能独立提交一组小改动，并清楚说出验证方法、风险点和回滚方案

## 每周固定节奏

- 周一：读结构和入口
- 周二：跟一次真实链路
- 周三：读测试
- 周四：做一个小改动
- 周五：复盘并输出笔记

## 学习版 Definition of Done

满足下面 5 条，才算真正学会一个模块：

1. 能口述这个模块负责什么
2. 能在 30 秒内定位主要入口
3. 能给出至少 1 条验证命令
4. 能说出至少 1 个容易出错的地方
5. 能写出最小改动方案和影响面

## 推荐命令清单

```bash
uv run pytest tests/test_api.py -q
uv run pytest tests/test_langgraph_engine.py -q
uv run pytest tests/test_llm_layer.py -q
pnpm --prefix frontend test
pnpm --prefix frontend typecheck
```

---

下一篇：`docs/mentor/06-practice-tasks.md`
