# 召回评测基线

## Goal

建立可重复的召回评测，跑出改造前的真实 API baseline，用数据决定改什么。

## 交付物

| 文件 | 内容 |
|---|---|
| `eval/retrieval_cases.json` | 8 个基准想法（中英各 4，覆盖 web/mobile/cli/api），含人工标注的 `known_competitors` 与缓存的 intent |
| `scripts/eval_retrieval.py` | 评测脚本，`--dry-run` / `--refresh-intents` / `--sources` / `--only` / `--out` |
| `eval/results/dryrun-before.json` | 改造前的查询快照（零成本，纯诊断） |
| `eval/results/baseline-2026-08-18.json` | 改造前的真实召回 baseline |

## 执行条件（必须与 after 运行一致）

```json
{"source_max_age_days": 730, "max_results_per_source": 10,
 "reddit_oauth_configured": false, "reddit_public_fallback": true}
```

**intent 是手工编写的，不是真实解析器产出的。** 配置的 LLM 网关返回 401
（`该令牌状态不可用`，纯 chat 请求也一样），`--refresh-intents` 跑不了。
手工 intent 严格按 `llm/prompts/intent_parser.txt` 的规则写（3–6 个具体可搜的
名词短语；中文输入才给 `keywords_zh`）。拿到可用 key 后应重跑
`--refresh-intents`，若 intent 变化则需重做 baseline。

> 附带发现：**LLM 网关失效意味着产品当前跑不了任何分析**，intent 解析是第一步。
> 这与本任务无关，但需要单独处理。

## Baseline 结果

### 各源贡献

| source | 总结果 | 出错 | 零结果 | 占比 |
|---|---|---|---|---|
| tavily | 252 | 0 | 0 | **38.8%** |
| hackernews | 187 | 0 | 0 | 28.8% |
| appstore | 154 | 0 | 0 | 23.7% |
| github | 33 | 0 | 3 | 5.1% |
| producthunt | 24 | 1 | 2 | 3.7% |
| **reddit** | **0** | **8** | 0 | **0.0%** |

### 已知竞品命中

整体 35/39（~90%）—— **比预期好得多**。但拆开看：

| case | Tavily 单源命中 | 全部源命中 |
|---|---|---|
| zh-web-research-notes | 3 | 5 |
| zh-mobile-hydration | 3 | 3 |
| zh-cli-deploy | 4 | 4 |
| zh-api-invoice-ocr | 4 | 4 |
| en-web-recruiting-crm | 5 | 5 |
| en-mobile-plant-care | 5 | 5 |
| en-cli-secrets | 5 | 5 |
| en-api-screenshot | 4 | 4 |

**Tavily 一个源就拿到 33/35，其余 5 个源合起来只多找到 2 个。**

### 时效分布

| 桶 | 数量 | 占比 |
|---|---|---|
| ≤30d | 48 | 7.4% |
| ≤90d | 20 | 3.1% |
| ≤180d | 42 | 6.5% |
| ≤1y | 78 | 12.0% |
| ≤2y | 95 | 14.6% |
| >2y | 115 | 17.7% |
| **unknown** | **252** | **38.8%** |

「未知」**100% 来自 Tavily**，其余 5 源均为 0%。

### 中文覆盖

| case | 结果数 | 结果中含中文比例 |
|---|---|---|
| zh-web-research-notes | 91 | 23.1% |
| zh-mobile-hydration | 81 | 40.7% |
| zh-cli-deploy | 86 | 11.6% |
| zh-api-invoice-ocr | 82 | 18.3% |

查询侧：中文想法产生 **29 条查询，含中文的只有 1 条**（3.4%）。

## 对原假设的修正

| 原假设 | 数据结论 |
|---|---|
| E1 中文几乎没接入 | ✅ **查询侧成立**（1/29）。但**结果侧不成立**：中文内容占 11.6–40.7%，不是 0。影响比我说的小 |
| E3 Reddit 缺 subreddit 定向是主要问题 | ❌ **失效**。Reddit 对全部 8 个用例、全部查询返回 **403**，贡献 0 条。在每个请求都 403 的前提下谈定向没有意义 |
| 「六源交叉验证」独立性弱 | ❌ **比我说的严重得多**。不是"重叠"，是**其余 5 源几乎不贡献独立的竞品信号**（+2/35） |
| 竞品发现问得不对 | ❌ **不成立**。90% 命中率。不该"修"它 |
| E2 时效被默认值中和 | ✅ 成立，且 17.7% 的证据超过 2 年、仅 7.4% 在 30 天内 |

## 新发现（只有跑起来才会暴露）

### F1 Tavily 把 `freshness_timestamp` 硬编码成 `None`

`src/ideago/sources/tavily_source.py:112`：

```python
"freshness_timestamp": None,
```

不是 API 不返回日期 —— 代码根本没去读。后果经实测量化：

```
无 freshness_timestamp: freshness=0.0  score=0.22600
有 freshness_timestamp: freshness=1.0  score=0.30600
差值 0.08 = 26.1% 的系统性劣势
```

**这个惩罚施加在贡献了 38.8% 证据、94% 竞品命中的主力源上。**
同时意味着 "Why Now" 与 `confidence.recency_score` 在 38.8% 的证据上是盲的。

这是本次 baseline 最重要的发现，也是纯代码审查发现不了的。

### F2 Reddit 公共回退被 403 全面封锁

8/8 用例、每条查询都 403。痛点信号渠道完全是暗的。
`reddit_public_fallback_limit` / `delay_seconds` 这些参数都没有意义 ——
未认证的 Reddit 搜索现在直接拒绝。

### F3 Product Hunt 触发 429

后段用例开始 429，topic 抓取也失败。24 条结果里还有 2 个用例是零。

### F4 查询构造把关键词拼成长串

`"research notes reference manager citation management academic notes alternative"`
—— 6 个词的长查询。另有裸查询 `saas` / `web app` / `apis` 出现在 HN 与
Product Hunt（无区分度），App Store 收到 `"research notes review problem"`
（App Store 是应用名匹配，不是全文搜索）。

## 对下一步的影响

原计划的优先级需要重排。**先做 F1**：一行改动，影响主力源的全部排序，
且能立刻用同一套评测验证。Reddit 定向（原 2.4）在 403 未解决前**没有意义**，
应改为先解决可达性（OAuth 凭据或换路径）。中文查询扩展（原 2.1）保留，
但预期收益要下调 —— 结果侧本来就有 11.6–40.7% 中文。

具体重排写进父任务 `implement.md`。

## 验证

```
uv run ruff check scripts/eval_retrieval.py   → All checks passed!
uv run python scripts/eval_retrieval.py --dry-run   → 8 cases, 无 API 调用
uv run python scripts/eval_retrieval.py --out ...   → 650 条结果, 39 个 (case,source) 组合
```
