# 执行计划：检索方式与取证渠道改造

## 硬性顺序

**① 评测基线 → ② 检索改造 → ③ 同口径重跑对比**

①  必须在任何检索逻辑改动之前完成并跑出 baseline。边改边测会污染基线，
"改好了"与"换了个问法"将无法区分。

③ 是本轮唯一能证明改进的证据。其余测试只能证明"改动符合意图"，
不能证明"召回变好"。

## Gate 定义

| Gate | 命令 |
|---|---|
| `G-py` | `uv run ruff check src tests scripts && uv run ruff format --check src tests scripts && uv run mypy src && uv run pytest` |
| `G-eval` | `uv run python scripts/eval_retrieval.py --cases eval/retrieval_cases.yaml --out <file>` |
| `G-dry` | `uv run python scripts/eval_retrieval.py --dry-run`（不调 API，只看生成的查询） |

## 阶段

### ① `08-18-retrieval-eval-baseline`（阻塞其余全部）

- [ ] **1.1** `eval/retrieval_cases.yaml`：中英各 4–6 个真实想法，
      覆盖 web / mobile / cli / api 四种 app_type，每个标注
      `known_competitors`（人工填，用于命中率）
- [ ] **1.2** `scripts/eval_retrieval.py`：
      `--cases` / `--sources` / `--out` / `--dry-run`；
      结果落 JSON；复用 `pre_filter.build_opportunity_score_breakdown` 算分
      （与线上排序同口径，不另造一套）
- [ ] **1.3** 先跑 `--dry-run`，把"中文想法实际产出了哪些查询"打出来 ——
      这一步本身就是 E1 的直接证据，且零成本
- [ ] **1.4** 跑真实 baseline，落盘 `eval/results/baseline-<date>.json` 并提交
- [ ] **1.5** 把 baseline 的关键结论写进本子任务 prd（空家族数、语言匹配率、
      时效分布、已知竞品命中率）
- [ ] Gate：`G-dry` + `G-eval` + `G-py`（脚本本身要过 lint/type）

**注意**：Reddit 当前是公共降级模式（OAuth 凭据为空、公共回退开启，
limit 10 + 1.5s 延迟）。baseline 必须在此条件下跑并**在结果里注明**，
否则后续对比口径不一致。

### ② `08-18-retrieval-method`（依赖 ①）

**优先级已按 baseline 数据重排**（原顺序基于代码推测，数据推翻了其中两项）。

- [ ] **2.1 Tavily 时效戳**（原本不在计划里，现为第一优先）
      `tavily_source.py:112` 把 `"freshness_timestamp": None` 硬编码。
      实测代价：无时效戳的结果 score 0.226 vs 有时效戳 0.306 —— **26.1% 的
      系统性排序劣势**，施加在贡献 38.8% 证据、94% 竞品命中的主力源上；
      并让 "Why Now" 与 `recency_score` 在 38.8% 的证据上是盲的。
      改：从 Tavily 响应里读实际日期字段；读不到时保持 None 但**不要让
      freshness 分量把它按"最旧"处理**。

- [ ] **2.2 Reddit 可达性**（原 2.4「subreddit 定向」降级至此之后）
      baseline：8/8 用例、每条查询 **403**，贡献 0 条。
      已验证**不是 UA 问题**（浏览器式 / Reddit 规范式 UA 同样 403）——
      Reddit 平台层面关闭了未认证 `search.json`，公共回退**结构性失效**。
      后果不只是"没结果"：`is_available()` 仍返回 True，流水线每次分析都要
      为必然失败的路径付 5 次查询 × 0.5–1.5s 延迟。
      改：对连续失败做熔断，不再宣称可用；把"需要 OAuth 凭据"明确暴露出来。
      **真正修好需要用户提供 REDDIT_CLIENT_ID / SECRET。**

- [ ] **2.3 查询构造**（原本不在计划里）
      长串拼接：`"research notes reference manager citation management academic
      notes alternative"`（6 词）；裸查询 `saas` / `web app` / `apis` 出现在
      HN 与 Product Hunt；App Store 收到 `"research notes review problem"`
      而 App Store 是应用名匹配。
      改：限制拼接词数、去掉无区分度的裸查询、App Store 只发名词短语。

- [ ] **2.4 中文查询扩展**（原 2.1，**预期收益下调**）
      查询侧确实只有 1/29 带中文，但**结果侧本来就有 11.6–40.7% 中文内容**，
      所以这不是"从 0 到 1"，是"从有到更好"。仍做，但不再是重点。

- [ ] **2.5 家族级时效分层**（原 2.2）+ **2.6 Reddit `t` 映射**（原 2.3）
      仅 7.4% 的证据在 30 天内、17.7% 超过 2 年，值得做；
      但 2.6 在 Reddit 恢复可达之前无法验证。

- [ ] **2.7 subreddit 定向** —— **阻塞**，等 2.2 解决可达性后再做。
      在每个请求都 403 的前提下做定向没有意义。

- [ ] Gate：`G-py`，每步 `--dry-run` 看查询变化，收尾同口径重跑 `G-eval`

### ③ `08-18-channel-hygiene`（可与 ② 并行）

- [ ] **3.1** 保留 `Platform.GOOGLE_TRENDS` 枚举成员（历史 `report_data`
      里可能已持久化该值，删枚举会让旧报告反序列化失败），
      加注释说明它没有对应 Source
- [ ] **3.2** 删掉 `pre_filter.py:135` 的 GOOGLE_TRENDS 特判分支及相关测试
- [ ] **3.3** 新增一致性测试：每个 `Platform` 成员要么有注册 Source，
      要么在显式豁免名单里 —— 防止将来再加枚举而忘了实现
- [ ] Gate：`G-py`

### ④ 收口（依赖 ①②③）

- [ ] **4.1** 同口径重跑 `G-eval`，落盘 `eval/results/after-<date>.json`
- [ ] **4.2** 与 baseline 逐指标对比，写进父任务产物。
      **重点看召回量有没有塌陷（R4）**，不是只看相关性涨了没有
- [ ] **4.3** 若相关性无可见提升，**如实记录并分析原因**，
      不得为了收尾而声称改进
- [ ] **4.4** `.trellis/spec/` 记录检索层新约定（语言维度、家族级时效、
      subreddit 定向策略、评测脚本的位置与用法）
- [ ] **4.5** 全栈 `G-py` + 前端四件套
- [ ] **4.6** 由 baseline/after 数据决定反馈闭环（E7）是否值得单独开一轮

## 回滚点

| 触发 | 动作 |
|---|---|
| 中文查询让某源查询数暴涨、触发配额或限流 | 收紧 `source_query_caps`；必要时中文查询只进 `pain`/`alternative` 两个家族 |
| subreddit 定向导致召回塌陷 | 定向查询本就是新增项，直接移除该家族的定向条目即可 |
| Tavily `advanced` 成本不可接受 | 退回 `basic`，只保留 `exclude_domains` |
| 重跑结果显示整体变差 | 逐项 revert，回到 baseline 状态；`eval/results/` 里两份数据都保留作为记录 |

## 当前状态

- 阶段：规划完成，等待开工授权
- 下一步：`task.py start 08-18-retrieval-eval-baseline`，先做 `--dry-run`

## 待确认（开工前）

`--dry-run` 零成本，可以立刻做。真实 API 跑 baseline 会消耗 Tavily / GitHub /
Product Hunt 配额并产生费用，需要明确许可。
