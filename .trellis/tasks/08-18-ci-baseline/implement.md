# 执行计划：恢复 CI 绿色基线

## 根因（读源码后确认，与初判有修正）

初判以为 `filter_raw_results` 内部调 `datetime.now()`，需要给生产函数加 `now` 参数。
**读源码后确认不是**：

- `pre_filter.py:175` → `_freshness_signal(raw.get("freshness_timestamp"), result.fetched_at)`
- `pre_filter.py:349-365` → `anchor = fetched_at`，`age_days = anchor - parsed`，
  再按 30/90/180/365/730 天分桶返回 1.0/0.8/0.6/0.4/0.2/0.0

**生产代码的时间来源已经是可注入的**（`RawResult.fetched_at`）。问题 100% 在测试：

- `models/research.py:40-43` → `fetched_at` 的 `default_factory` 是
  `datetime.now(timezone.utc)`
- `tests/test_pre_filter.py:17-30` 的 `_raw()` helper **不设置 `fetched_at`**
  → 取到「今天」
- 而 `freshness_timestamp` 被钉死在 `"2026-03-20T00:00:00Z"`

于是 `age_days` 随真实日期增长：写用例时 ≤90 天 → freshness 0.8；
今天 2026-08-18 已 151 天 → 落进 `<=180` 桶 → 0.6。
差值 `(0.8 - 0.6) × 0.08 = 0.016`，而断言只差 `0.52 - 0.51912 = 0.00088`。
算术完全吻合，根因坐实。

**结论：本任务不需要改任何生产代码**，风险面从「改打分函数」降到「只改测试」。
父任务 `design.md` 的 D3 需要相应修正。

## 全量排查结果（R3）

`git grep -nE '"20[0-9]{2}-[0-9]{2}-[0-9]{2}' -- tests/` 命中 45 处，分布在 5 个文件：

| 文件 | 命中 | 是否时间炸弹 | 判定依据 |
|---|---|---|---|
| `tests/test_pre_filter.py` | 4 | ✅ **是** | 喂给 `freshness_timestamp`，与默认 `fetched_at`(=now) 做差分桶 |
| `tests/test_date_utils.py` | 5 | ❌ 否 | `test_get_current_date_*` 用 `monkeypatch.setattr(date_utils_module, "datetime", FixedDateTime)` 完整固定了时钟，断言值来自被固定的 now |
| `tests/test_sources.py` | 33 | ❌ 否 | 全部是 mock HTTP 响应里的透传字段；测试从不给 source 传 `max_age_days`，各 source 默认 `max_age_days=0` → `github_source.py:86` 的 cutoff 分支不进入，无任何时间比较 |
| `tests/test_api.py` | 6 | ❌ 否 | `freshness_hint` / `reset_at` / `created_at` 都是模型字段透传或 mock 出的 Supabase 行，无衰减计算 |
| `tests/test_llm_layer.py` | 1 | ❌ 否 | `release_date_iso` 是 LLM 返回结构里的透传字符串 |

只有 `test_pre_filter.py` 需要处理。

## 步骤

- [x] **S1** 在 `tests/test_pre_filter.py` 顶部定义固定锚点

  ```python
  # 打分里的 freshness 分量 = f(freshness_timestamp, RawResult.fetched_at)。
  # 若 fetched_at 用默认值（挂钟 now），用例结果会随日期漂移并在某天自己变红。
  # 这里把 fetched_at 钉死，并让 fixture 时间戳落在锚点前 60 天，
  # 即 ">30d, <=90d" 这个 freshness=0.8 的桶——也就是这些断言最初被写出来时的桶。
  _FIXED_FETCHED_AT = datetime(2026, 5, 19, tzinfo=timezone.utc)
  _RECENT_TIMESTAMP = "2026-03-20T00:00:00Z"
  ```

- [x] **S2** `_raw()` helper 增加 `fetched_at` 参数，默认 `_FIXED_FETCHED_AT`，
      透传给 `RawResult`

- [x] **S3** 把 4 处硬编码 `freshness_timestamp` 字面量替换为 `_RECENT_TIMESTAMP`
      （`2026-03-22` 与 `2026-03-20` 同属一个桶，统一以消除无意义差异）

- [x] **S4** 把魔法阈值断言换成表达意图的断言（`test_pre_filter.py:127`）

  ```python
  # before
  assert breakdown.score >= 0.52

  # after
  assert breakdown.freshness == pytest.approx(0.8)   # 锁住锚点，时间独立性本身被测
  assert breakdown.score > popularity_breakdown.score
  ```

  保留 `assert getattr(breakdown, expected_component) > 0.55`（测分量识别，不脆弱）
  与 `assert breakdown.score - popularity_breakdown.score >= 0.15`（已是相对断言）

- [x] **S5** 新增回归守卫，防止以后有人再写出会腐烂的 fixture

  ```python
  def test_fixture_fetched_at_is_pinned() -> None:
      """Guard: fixtures must not inherit wall-clock fetched_at, or scoring tests rot."""
      assert _raw(Platform.TAVILY).fetched_at == _FIXED_FETCHED_AT
  ```

- [x] **S6** 跑 Gate `G-py`，确认 **0 failed** 且覆盖率 ≥ 84.47%

- [x] **S7** 时间独立性验证：确认新增的 `breakdown.freshness == 0.8` 断言在
      任意系统日期下都成立（因为不再依赖 now），并记录验证方式

- [x] **S8** 修正父任务 `design.md` 的 D3 段落，把「给 `filter_raw_results` 加
      `now` 参数」改为「测试侧钉死 `fetched_at`」，避免设计与实现分叉

- [ ] **S9** 提交 `fix(tests): pin fetched_at so pre-filter scoring tests are time-independent`

## 验证命令

```bash
uv run pytest tests/test_pre_filter.py -q --no-cov     # 快速确认
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest                                          # 完整 Gate G-py
```

## 回滚点

改动仅限 `tests/test_pre_filter.py` 一个文件，无生产代码变更。
出问题直接 `git checkout -- tests/test_pre_filter.py`。


## 执行结果（2026-08-18）

### 与计划的偏差

跑完 S6 后发现覆盖率从基线 84.47% 掉到 84.45%。定位到 `pre_filter.py`
的 `_freshness_signal` 分桶：**原来 0.6 那个桶只是被日历「偶然」覆盖到的**
——fixture 时间戳与挂钟 now 的距离刚好落在 `<=180` 桶里。钉死 `fetched_at`
之后距离变成 60 天，那个桶就没人走了。

也就是说：不只是断言随日期漂移，**覆盖率本身也随日期漂移**。这比原本诊断的
问题更严重一层。

因此追加了计划外的一步：

- [x] **S6b** 新增 `TestFreshnessSignal`，参数化覆盖全部 6 个分桶的边界值
      （0/30/31/90/91/180/181/365/366/730/731/5000 天），外加未来时间戳钳位、
      不可解析时间戳、naive/Z 后缀/带偏移时间戳的归一化、以及非 UTC 锚点归一化。
      `_freshness_signal` 与 `_parse_iso8601` 从此有直接测试，不再依赖偶然覆盖。

### 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 124 files already formatted
uv run mypy src                            → Success: no issues found in 84 source files
uv run pytest                              → 803 passed, 0 failed
覆盖率                                      → 84.62%（基线 84.47%，+0.15pp）
src/ideago/pipeline/pre_filter.py 覆盖率     → 89% → 96%
```

时间独立性经验证据（一次性脚本，未提交）：把 `pre_filter.datetime.now` 替换为
一个会 raise 的实现后跑打分路径，正常完成且未触发——证明打分路径完全不读挂钟。
输出 `freshness=0.8, score=0.53512`，与手算 `0.51912 + (0.8-0.6)×0.08` 逐位吻合。

### AC 核对

| AC | 结果 |
|---|---|
| pytest 0 failed | ✅ 803 passed |
| 日期推移后仍通过 | ✅ 静态（唯一 `now()` 在 `max_age_days>0` 分支，测试不走）+ 经验（now booby-trap 未触发） |
| 日期字面量全量排查 | ✅ 45 处命中，5 文件，仅 `test_pre_filter.py` 是炸弹，清单见上 |
| ruff / format / mypy | ✅ 全绿 |
| 覆盖率 ≥ 84.47% | ✅ 84.62% |
| 生产调用路径行为不变 | ✅ 零生产代码改动，`git diff --stat src/` 为空 |
