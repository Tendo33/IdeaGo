# 检索方式改造

## 结论：本轮只保留 1 项改动，另 1 项经数据否决后撤回

评测起了作用——它否决了两个我基于代码推测的方案。这份记录的价值主要在
「什么没做成、为什么」。

## 保留：`_freshness_signal` 的未知时效改为中性先验

`pre_filter.py`：无法解析时效戳时原本返回 `0.0`，而「超过 2 年」返回 `0.2`。
即**「不知道多老」被打得比「确定很老」还差**，是最差档。改为中性先验 `0.3`
（介于 >1y 的 0.4 与 >2y 的 0.2 之间）。

### 必须说明：这在当前数据上是 no-op

我最初宣称它能消除「26.1% 的系统性排序劣势」。**该说法在当前数据上不成立**：

- `filter_raw_results` 是**按源分别排序**的，不做跨源比较
- baseline 显示没有任何源是混合的：Tavily 252/252 未知，其余 5 源 0/N
- 所以 Tavily 全部结果同等 +0.024，**源内顺序完全不变**
- `_build_fallback_opportunity_score` 也不消费单条结果的分数

保留它的理由不是"它改善了什么"，而是**它修正了一个语义错误**：一旦任何源
开始返回部分日期（例如启用 Tavily 的 `topic=news`，实测该模式确实返回
`published_date`），旧逻辑会立刻开始错误地惩罚未标注日期的那部分。

### 顺带更正一个诊断

我先前说 `tavily_source.py:112` 的 `"freshness_timestamp": None` 是
「代码从来没去读日期」。**实测后更正**：Tavily 的 `topic=general`（代码当前
用的模式）**响应里根本没有日期字段**；只有 `topic=news` 才返回
`published_date`（RFC 2822 格式）。所以那行硬编码是诚实的，缺陷在打分侧。

## 撤回：查询构造中的裸 hint 组合

### 改动内容

`hn_extra` / `ph_topics` / `appstore_genre` 原本被**原样**当作查询发出，
产生 `saas` / `web app` / `apis` 这类无区分度的裸查询。而 GitHub 与 Reddit
早已在把 hint 与关键词组合。改为让这三个平台follow同一模式。

假设：裸查询召回的是噪声，组合后应更精准。

### 数据否决了这个假设

同口径重跑（`eval/results/after-2026-08-18.json`）：

| source | baseline | after | Δ |
|---|---|---|---|
| tavily | 252 | 264 | +12 |
| hackernews | 187 | 150 | **−37** |
| appstore | 154 | 153 | −1 |
| github | 33 | 33 | 0 |
| producthunt | 24 | 24 | 0 |
| reddit | 0 | 0 | 0 |
| **合计** | **650** | **624** | **−26 (−4%)** |

已知竞品命中：35 → 36（满分 39），**在噪声范围内**。

关键的是 HackerNews 的分数中位数**在每一个用例都下降**：

```
zh-web-research-notes   24 → 21    0.2080 → 0.1659  ↓
zh-mobile-hydration     12 →  5    0.2080 → 0.1070  ↓
zh-cli-deploy           23 → 21    0.1920 → 0.1501  ↓
zh-api-invoice-ocr      26 → 25    0.1869 → 0.1495  ↓
en-web-recruiting-crm   28 → 21    0.1920 → 0.1311  ↓
```

不是"用量换质"，是**量和质都降了**。按父任务 R4（不得降低召回量）与
implement.md 4.3（无可见提升则如实记录，不得为收尾而声称改进），**已撤回**
（`git checkout -- src/ideago/pipeline/query_builder.py tests/test_query_builder.py`）。

### 但这次失败暴露了更值得追的问题

为什么裸 `"web app"` 反而拿到更高分的 HN 结果？因为 `opportunity_score` 里
popularity（points/comments）权重很重，而裸查询命中的是**热门但离题**的大帖，
组合查询命中的是**贴题但冷门**的小帖。

**所以指标本身偏向热度而非相关性。** 这解释了为什么"更精准的查询"会被评分
判为更差。在打分函数修正之前，任何以该分数为准绳的查询优化都会被系统性误导。

这比原来的查询构造问题更根本，已记入父任务待办。

## 未做及原因

| 项 | 原因 |
|---|---|
| 2.2 Reddit 可达性 | 已验证 **不是 UA 问题**（当前 UA / 浏览器式 / Reddit 规范式，三种全部 403）。Reddit 平台层面关闭了未认证 `search.json`，公共回退**结构性失效**。真正修好需要用户提供 `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` |
| 2.7 subreddit 定向 | 阻塞于上一条。每个请求都 403 时做定向没有意义 |
| 2.4 中文查询扩展 | 未做。baseline 显示结果侧本来就有 11.6–40.7% 中文，收益远小于预期；且在打分函数偏向热度的情况下，无法判断中文查询是改善还是恶化 |
| 2.5 家族级时效分层 | 未做。同上，缺可信的质量指标 |

## 验证证据

```
uv run ruff check src tests scripts        → All checks passed!
uv run ruff format --check src tests scripts → 140 files already formatted
uv run mypy src                            → Success: no issues found in 90 source files
uv run pytest                              → 892 passed, 0 failed, 覆盖率 84.86%
```

`tests/test_pre_filter.py` 新增 2 个用例：未知时效得到中性先验、
且严格介于"确定很老"与"确定很新"之间。

两份评测数据都保留在 `eval/results/`，作为下一轮的对照基准。

---

# 第二轮：打分函数（2026-08-19）

## 方法论修正：先建立不受打分影响的指标

第一轮的教训是「用打分函数当指标去评价打分函数」不成立。因此先升级评测：

1. **保存原始结果**到语料（`eval/results/corpus-2026-08-19.json`，883 KB），
   之后调指标或调打分函数都不必再烧 API
2. **新增 `--rescore`**：从语料离线重算，零 API 调用
3. **新增排名指标**：MRR、P@5、首命中排名 —— 基于人工标注的
   `known_competitors`，跨打分改动依然可比

### 排名基线

| source | MRR | P@5 | 首命中排名(中位) |
|---|---|---|---|
| tavily | 0.875 | 0.750 | **1** |
| appstore | 0.194 | 0.100 | 9 |
| github | 0.167 | 0.080 | 2.5 |
| hackernews | 0.100 | 0.050 | **21** |
| producthunt | 0.000 | 0.000 | 无命中 |

Tavily 几乎总是第一条就命中；**HackerNews 的已知竞品中位排在第 21 位**。

## 根因确认：打分函数没有相关性概念

`build_opportunity_score_breakdown` 的全部输入是：热度、痛点/替代/商业**词汇**、
时效、竞争密度。`matched_query` 虽然进了 `signal_text`，但只被扫描有没有痛点
词汇，**从不用来判断结果是否切题**。

叠加 `competitor_discovery` 家族的信号基线是 `(0.0, 0.08, 0.0)` —— 近乎为零，
所以该家族的结果**几乎纯按热度排序**，还要扣 0.38 的竞争惩罚。

这解释了第一轮的反常：更精准的查询召回了贴题但冷门的帖子，而打分器偏好热门。

## 尝试并撤回：查询词重叠作为相关性分量

加入 `_query_relevance`：统计 `matched_query` 的实义词在 title+description 中的
覆盖率（剔除模板词与停用词），作为新的打分分量。

离线扫权重（全部 rescore↔rescore 同口径）：

| weight | MRR | P@5 |
|---|---|---|
| **0.00（基线）** | **0.2845** | **0.171** |
| 0.05 | 0.2888 (+0.004，噪声级) | 0.166 (−0.005) |
| 0.10 | 0.2566 (−0.028) | 0.143 (−0.028) |
| 0.20 | 0.2363 (−0.048) | 0.154 (−0.017) |
| 0.30 | 0.2363 (−0.048) | 0.154 (−0.017) |

**单调恶化：任何权重都不优于基线，权重越大越差。** 是分量本身错了，不是没调好。

### 为什么错

**竞品是具名实体，不是词匹配文档。** Zotero 的页面标题是
「Zotero | Your personal research assistant」，不会重复
「reference manager」「citation management」这些品类词。
字面词重叠恰好惩罚了最该排在前面的品牌页。

已撤回（`git diff` 确认 `pre_filter.py` 只剩 freshness 一处改动）。

## 顺带修掉的评测自身缺陷

撤回后离线指标没回到之前引用的 0.2911/0.217，查出原因：`_serialize` 把
`description` 截断到 400 字符，而打分器要扫描 description 里的痛点/商业词汇，
所以**离线回放与线上运行不一致**。已改为完整保留（只丢弃打分不读的
`raw_content`）。

因此本文所有对照都以 **rescore↔rescore** 为准（基线 0.2845 / 0.171）。
`corpus-2026-08-19.json` 是在修复前抓的，其 description 已截断，
下次重抓即可得到忠实语料。

## 本轮结论

两个看似合理的方案连续被数据否决：

1. 查询构造（裸 hint 组合）→ 量与质双降，撤回
2. 查询词重叠相关性 → 单调恶化，撤回

**真正的交付物是评测基础设施**：现在有了固定语料 + 离线重打分 + 跨打分可比的
排名指标。下一个尝试的成本从「5 分钟 + API 费用」降到「秒级 + 0」。

### 下一步的候选（不再靠推测，需逐个离线验证）

- 提高 `competitor_discovery` 的信号基线 / 降低其 0.38 竞争惩罚
- 把品牌名识别（具名实体）而非词重叠作为相关性代理
- 降低 popularity 在总分中的净权重
- HackerNews 首命中中位第 21 位是最大的单点，值得单独攻

以上都能用 `--rescore` 在秒级内证伪。

---

# 第三轮：契约缺陷（2026-08-19）

## 方法转向

前两轮失败的共同点：**猜一个启发式去改善模糊的质量指标**。那类工作只能靠实验
证伪，两次被否决是正常结果，不是执行问题。

这一轮改做**结构性缺陷**——纯代码可证、可写回归测试、不依赖坏掉的 LLM 网关和
缺失的 Reddit 凭据。两项都落地了。

## 修复：planner 与打分器的 family 词表不匹配

LLM planner 产出 `QueryFamily` 枚举值，打分器 `_FAMILY_BASE_COMPONENTS` 用的是
另一套词表，**6 个里 3 个对不上**，落到 `.get(family, (0.0, 0.0, 0.0))` ——
信号基线全零，结果纯按热度排序。

`_normalize_planned_families` 把 planner 的 family 原样传下去，中间没有映射表。

实测同一条 Zotero 结果：

| query_family | score |
|---|---|
| `adjacent_analogy`（LLM 产出） | 0.204 |
| `alternative_discovery`（打分器原生同义家族） | 0.589 |

**差 2.9 倍。**

### 必须说明：这是潜在缺陷，当前未生效

我先在 `corpus-2026-08-19.json` 实测，发现 **100% 的 family 打分器都认识**
（competitor_discovery 468 条、pain_discovery 57 条等）——因为 LLM 网关 401，
`query_plan` 为 None，走的是确定性模板路径，模板产出的就是打分器原生名字。

所以 `--rescore` 前后指标完全不变（MRR 0.2845 / P@5 0.171），这是**预期结果**，
不是"改动无效"。它会在 LLM 恢复的那天变成「替代品发现悄悄失效」。

修复方式是加 `_PLANNER_FAMILY_ALIASES` 映射表 + 一条断言「任何 `QueryFamily`
都不能落到零基线」的回归测试，这样以后新增枚举值忘记映射会直接测试失败。

## 修复：分析准入控制（并发无上限）

不属于检索方式，但同批发现、同批提交。

已验证事实：`PipelineNodes` 在 `run()` **内部**构造，所以两个名为 `global` 的
semaphore 实际是**每次分析各一份**；`_run_pipeline` 是 `create_task` 发射后不管；
`grep -rn "Semaphore" src/ideago/api/` **无结果**。

限流是 10 次/60 秒/用户，但一次分析要跑几分钟 → 单个用户可压 10 个在途分析
× 6 个并发外部 HTTP，全在单进程单事件循环上。**限流挡的是请求速率，挡不住在途
工作量。**

新增 `max_concurrent_analyses`（默认 8）与 `max_concurrent_analyses_per_user`
（默认 2），先查单用户闸再查全局闸，使得单账号无法占满全局额度。

## 顺带：评测语料的可信度

发现 `corpus-2026-08-19.json` 中 **653 条有 418 条（64%）的 description 被截到
400 字符**，而打分器正要读这个字段。已在 `eval/results/README.md` 显式标注：
同语料内的 A/B 仍然有效，但不能当作真实排序的估计。

## 验证证据

```
uv run ruff check src tests scripts          → All checks passed!
uv run ruff format --check src tests scripts → 141 files already formatted
uv run mypy src                              → Success: no issues found in 90 source files
uv run pytest                                → 904 passed, 0 failed, 覆盖率 84.91%
```

新增 `tests/test_admission_control.py`（7 例）与 `TestPlannerFamilyAliases`（5 例）。

## 剩余同类候选（结构性、可证）

三条全部完成，见下节。

---

# 第四轮：三项运行时缺陷（2026-08-19）

## ① 单次分析无总时限

`await orchestrator.run(...)` 外没有任何 `wait_for`。分阶段超时约束不了总时长：

| 阶段 | 最坏 |
|---|---|
| parse_intent | 120s × 3 次重试 × 端点数 |
| fetch_sources | ceil(6/3) × 30s = 60s |
| extract_map | ceil(6/3) × 60s = 120s |
| analyze | 60s |

无 fallback 端点时合计约 **10 分钟**；配 2 个 fallback 端点则 parse_intent 一节
就是 1080s，总计 **超过 22 分钟**。

这条在第三轮之后变得更要紧：准入闸只有 8 个全局槽位，**一个卡住的分析会永久占槽**，
闸门会退化成慢性死锁。总时限是准入控制能成立的前提。

新增 `analysis_total_timeout_seconds`（默认 600），超时走完整终态：退配额 +
持久化 `failed` / `PIPELINE_TIMEOUT` + 推送终态事件，与其他结局一样释放槽位。

### 关键设计约束

`wait_for` 夹在「用户主动取消」和「流水线」之间，两者不能混淆：内部超时以
`TimeoutError` 浮现，`task.cancel()` 仍以 `CancelledError` 穿透。
`except asyncio.TimeoutError` 必须排在 `except Exception` 之前（前者是后者的子类）。
已有专门测试钉住这一点。

## ② Reddit 公共回退熔断

### 先修正我自己的错误诊断

我先前称「5 条查询 × 1.5s = 7.5s 浪费」。**实测证否**：403 在
`await asyncio.sleep(delay)` 之前抛出，异常路径根本不睡。日志时间戳全部相同。

另外「`is_available()` 返回 True」也需要限定：代码默认
`enable_public_fallback=False`，`is_available()` 正确返回 False。是本机 `.env`
显式设了 `REDDIT_ENABLE_PUBLIC_FALLBACK=true` 才走上必然 403 的路。

### 真实代价与修复

回退路径是串行的（`max_concurrency=1` + `request_lock`），所以真实浪费是
**N 次串行 HTTP 往返**，每次都在确认同一件已知的事。

加熔断：首次 401/403 后本实例不再尝试。实测 5 条查询的 HTTP 请求
**从 5 次降到 1 次**。429 不触发熔断——限流是暂时的，封禁不是。

## ③ Product Hunt 429 无退避

所有非 200 一视同仁。实测语料 8 个用例中 **1 个（en-api-screenshot）因单次 429
整源归零**。

加一次重试并遵循 `Retry-After`，但**仅当等待能装进源级预算**（上限 8s）；
超出则快速失败，把时间留给其他源。无 header 时默认退避 2s；HTTP-date 格式
视为不可用而非猜测时钟偏移。

## 验证证据

```
uv run ruff check src tests scripts          → All checks passed!
uv run ruff format --check src tests scripts → 141 files already formatted
uv run mypy src                              → Success: no issues found in 90 source files
uv run pytest                                → 915 passed, 0 failed, 覆盖率 84.97%
```

新增测试：`TestTotalTimeBudget`（3 例，含取消与超时不得混淆）、
`TestProductHuntRateLimitBackoff`（5 例）、`TestRedditPublicFallbackBreaker`（3 例）。

## 本轮方法论小结

四轮下来的分野很清楚：

- **猜启发式改善模糊指标**（第一、二轮）→ 2 次被数据否决，全部撤回
- **修结构性缺陷**（第三、四轮）→ 5 项全部落地，每项都有可复现的量化证据

而且第四轮里我自己的两条诊断（Reddit sleep 浪费、`is_available()` 返回值）
都是先测量才发现说错了。**先量化再动手**是这两轮成立的关键。
