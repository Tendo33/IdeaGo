# 恢复 CI 绿色基线

## Goal

消除测试套件里的挂钟时间依赖，让 `uv run pytest` 在任意日期都稳定通过，
恢复可信的验证基线。这是父任务 `08-18-full-audit-remediation` 下所有其他
子任务的硬前置。

## Background

干净 HEAD (`93cddb6`) 上实测：

```
FAILED tests/test_pre_filter.py::TestFilterRawResults::
  test_signal_rich_results_can_outrank_popularity_only_results[alternative_discovery-...]
FAILED tests/test_pre_filter.py::TestFilterRawResults::
  test_signal_rich_results_can_outrank_popularity_only_results[commercial_discovery-...]
2 failed, 777 passed, 覆盖率 84.47%
```

失败断言（`tests/test_pre_filter.py:127`）：

```
>       assert breakdown.score >= 0.52
E       assert 0.51912 >= 0.52
E        +  where 0.51912 = OpportunityScoreBreakdown(
             pain_intensity=0.12, solution_gap=0.15, commercial_intent=1.0,
             freshness=0.6, competition_density=0.112, score=0.51912)
```

根因：用例把 `freshness_timestamp` 写死为 `"2026-03-20T00:00:00Z"`，而
`pre_filter` 的 freshness 分量随**真实当前时间**衰减。今天是 2026-08-18，
已过约 151 天，`freshness` 衰减到 0.6，加权后总分越过 `0.52` 阈值 0.00088。

写用例时（3 月）通过，之后某一天自己变红。CI 在 `saas` 上已红一段时间，
而项目 `CLAUDE.md` 要求「声明完成之前必须有新的验证证据」——这条规则事实上
已被一个红的 gate 破坏。

## Requirements

### R1 测试 fixture 不得继承挂钟时间

读源码后确认：生产代码的时间来源**已经是可注入的**——`_freshness_signal`
以 `RawResult.fetched_at` 为锚点，而非 `datetime.now()`。问题在于
`RawResult.fetched_at` 的 `default_factory` 是 `datetime.now(timezone.utc)`，
测试 helper `_raw()` 不设置它，于是拿到「今天」，与钉死的
`freshness_timestamp` 做差后随日期漂移。

因此要求是：测试 fixture 必须显式钉死 `fetched_at`。**本任务不改任何生产代码**。

### R2 断言测意图而非测小数

`assert breakdown.score >= 0.52` 这类魔法阈值断言，任何一次打分权重微调都会
误伤。用例真正要验证的意图是「信号丰富的结果能压过只有热度的结果」，
断言应该直接表达这个意图。

保留 `assert getattr(breakdown, expected_component) > 0.55`——这条测的是
分量本身被正确识别，不是脆弱阈值。

### R3 全量排查，不止修这两个用例

必须扫描整个 `tests/` 目录，找出所有硬编码日期字面量，逐个判断是否参与
时间衰减/新鲜度/过期计算。凡是参与的，全部注入固定时间源。产出一份清单
记录在本任务的 `notes` 或 `implement.md` 里。

### R4 不降低覆盖率

改动后 pytest 覆盖率不得低于 84.47%。

## Constraints

- 只改 `src/ideago/pipeline/pre_filter.py` 的函数签名（新增关键字参数，带默认值）
  与 `tests/` 下的用例；不改打分权重、不改任何业务逻辑
- 不新增依赖（不引入 `freezegun` 之类）——项目现有做法是显式传 `now`
  （见 `pipeline/nodes.py` 的 `build_freshness_hint(now=...)`），沿用它
- 保持 `mypy src` 零报错

## Acceptance Criteria

- [ ] `uv run pytest` 在当前日期通过：**0 failed**
- [ ] 把系统时间概念性推后一年（用固定 `now` 参数模拟）后，
      `tests/test_pre_filter.py` 仍然通过——即用例结果不再随日期变化
- [ ] `git grep -nE '"20[0-9]{2}-[0-9]{2}-[0-9]{2}' tests/` 的每一处命中都已被
      审查，清单记录在 `implement.md`，参与时间计算的全部处理完毕
- [ ] `uv run ruff check src tests scripts` 通过
- [ ] `uv run ruff format --check src tests scripts` 通过
- [ ] `uv run mypy src` 通过
- [ ] 覆盖率 ≥ 84.47%
- [ ] `pre_filter_node` 的生产调用路径未传 `now`，行为与改动前逐字节一致
      （通过现有其他用例保证）

## Out Of Scope

- 不调整打分权重或阈值本身（那是产品决策，不在本任务）
- 不重构 `pre_filter.py` 的其他部分
- 前端测试不在本任务范围（前端 209 测试当前全绿）
