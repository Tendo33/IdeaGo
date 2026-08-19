# 技术设计：检索方式与取证渠道改造

## D0 顺序是设计的一部分

```
① 建评测 + 跑 baseline   ←── 必须最先，且此阶段不改任何检索逻辑
② 修显性问题（中文/Reddit/Tavily/时效）
③ 同口径重跑，与 baseline 对比
④ 由数据决定要不要做反馈闭环（本轮不做）
```

把 ① 单独隔出来的理由：如果边改边测，baseline 就被污染了，
"改好了"和"换了个问法"分不开。

## D1 评测基线（子任务 1）

### 形态

`scripts/eval_retrieval.py`，不是 pytest。理由：它跑真实 API、有费用、
耗时以分钟计、结果是**给人看的数据**而不是通过/失败断言。放进 pytest 会
污染 CI 的语义。

```bash
uv run python scripts/eval_retrieval.py \
    --cases eval/retrieval_cases.yaml \
    --sources tavily,reddit,github \
    --out eval/results/baseline-2026-08-18.json
```

### 基准用例集

`eval/retrieval_cases.yaml`，每个用例是一个真实想法 + 人工标注的期望特征：

```yaml
- id: zh-note-app
  query: 给研究者用的笔记工具，能自动整理文献引用
  lang: zh
  expect_signals: [pain, alternative, commercial]
  known_competitors: [Zotero, Notion, Obsidian]   # 人工填，用于算命中率
- id: en-b2b-crm
  query: A lightweight CRM for recruiting agencies
  lang: en
  ...
```

中英各 4–6 个，覆盖不同 `app_type`（web / mobile / cli / api），
因为编排画像按 app_type 切换预算，不同画像的召回表现应该分开看。

### 量什么

| 指标 | 怎么算 | 为什么 |
|---|---|---|
| 每源每家族返回量 | 直接计数 | R4：防止"更精准"变成召回塌陷 |
| 空家族数 | 返回 0 条的 (源, 家族) 组合数 | 直接暴露"这个源在这个家族上是哑的" |
| 已知竞品命中率 | `known_competitors` 在结果标题/URL 中的出现比例 | 唯一有人工基准的相关性指标 |
| 语言匹配率 | 中文用例的结果里中文内容占比 | 量化 E1 的实际影响 |
| opportunity score 分布 | 复用 `pre_filter.build_opportunity_score_breakdown` | 与线上排序口径一致，不另造一套 |
| 时效分布 | 结果 `freshness_timestamp` 的分桶 | 量化 E2（Reddit `t=all`）的实际影响 |

**不做**人工相关性打分：主观、不可重复、成本高。已知竞品命中率虽然窄，
但客观且可重跑。

### 安全阀

- `--dry-run` 只打印将要发出的查询，不调 API。这本身就有诊断价值：
  能直接看到"中文想法产出了哪些查询"
- `--sources` 限定范围，避免每次都烧全部配额
- 默认不进 CI

## D2 中文接入全家族（子任务 2）

### 现状

`query_builder.py` 的 6 个 `_build_*_families` 全部只吃 `keywords`
（即 `keywords_en`），只有 `_build_tavily_families` 额外插了一条中文竞品查询。

### 方案

不给每个平台重写一套中文模板 —— 那会把 6 个函数各自的复杂度翻倍。
改为**在家族模板层引入语言维度**：

```python
# 现在：模板写死英文
pain_queries.append(f"{joined} pain points")

# 之后：模板按语言取词
for term in _family_terms("pain", intent.output_language):
    pain_queries.append(f"{joined} {term}")
```

`_family_terms(family, lang)` 是一张小表：

```python
_FAMILY_TERMS = {
    "pain":        {"en": ["pain points", "problem"], "zh": ["痛点", "难用", "吐槽"]},
    "alternative": {"en": ["alternative"],            "zh": ["替代", "平替"]},
    "commercial":  {"en": ["pricing"],                "zh": ["价格", "收费"]},
    "migration":   {"en": ["switch from"],            "zh": ["从…迁移", "换掉"]},
    "workflow":    {"en": ["workflow", "recommend"],  "zh": ["工作流", "推荐"]},
}
```

关键点：中文查询用 `keywords_zh` 拼，英文查询用 `keywords_en` 拼，
**两者都发**（中文想法在英文社区同样可能有证据）。这也是 R4 的保障 ——
只加不减，召回量不会因此下降。

配额影响：查询数会增加。由现有的 `source_query_caps` 与
`role_query_budgets` 兜住，不需要新机制。但 baseline 对比时要留意
每源查询数的变化。

### 语言从哪来

`intent.output_language` 已存在（`nodes_confidence` / `nodes_report_assembly`
都在用）。不新增字段。

## D3 Reddit 定向与时效（子任务 2）

### subreddit 定向

Reddit 搜索支持 `restrict_sr=on` + 在 `q` 里写 `subreddit:xxx`，
公共 `search.json` 与 OAuth 路径都支持。

subreddit 从哪来？两种，**先做前者**：

1. **从 intent 的 app_type + 关键词映射**一张静态表
   （`web → r/SaaS, r/webdev`；`cli → r/commandline`；通用 → `r/SideProject`,
   `r/Entrepreneur`, `r/smallbusiness`）。确定、可测、零额外成本。
2. 让 LLM 在 intent 阶段推荐 subreddit。更灵活但引入一次额外 LLM 调用
   与不可预测性 —— 等 baseline 证明静态表不够用再说。

**保留全局查询**：定向查询是**新增**的家族条目，不替换现有全局查询。
同样是 R4 的保障。

### 时效映射

问题不在于 `t` 没传，而在于 730 天映射成 `all`，且 90/180/365 全塌进 `year`。

```python
# 现在：粗到失真
if max_age_days <= 365: return "year"
return "all"

# 之后：让"两年"仍然是一个约束，而不是"不限"
if max_age_days <= 365: return "year"
if max_age_days <= 730: return "year"   # 两年→仍按年过滤，而不是放开
return "all"
```

更根本的是 **D4 的时效分层**：`why-now` / `commercial` 家族用短窗口，
`competitor` 家族用长窗口。Reddit 的 `t` 只有 day/week/month/year/all 五档，
所以分层要在**家族级**而不是全局级生效。

## D4 时效分层（子任务 2）

`source_max_age_days` 现在是一个全局值，被所有家族共用。改为：

```python
_FAMILY_MAX_AGE_DAYS = {
    "pain_discovery":       365,   # 痛点会持续，但太老的没意义
    "commercial_discovery": 180,   # 定价变化快
    "launch_discovery":     180,   # "why now" 的主要来源
    "competitor_discovery": 730,   # 竞品盘点可以看得久
    "ecosystem_discovery":  730,
}
```

默认值仍从 `source_max_age_days` 取，表里只写**偏离全局值**的家族。
这样既保持向后兼容，又让 "Why Now" 不再拿两年前的证据回答。

## D5 Tavily 提档与定向（子任务 2）

- `search_depth`: 对 `pain` / `commercial` 家族用 `advanced`，
  其余保持 `basic`（advanced 更贵更慢，不全量开）
- `exclude_domains`: 排掉内容农场与聚合站（先列一小组明确的）
- 不用 `include_domains`：会把广度来源变成窄来源，与它"广度召回"的定位冲突

## D6 幽灵渠道清理（子任务 3）

`GOOGLE_TRENDS` 的处理要同时动三处，缺一处就会留下不一致：

1. `models/research.py` 的 `Platform` 枚举
2. `pre_filter.py:135` 的专属打分分支
3. 引用它的测试

**注意**：`Platform` 是持久化进 `report_data` JSON 的。历史报告里可能已经
存在该值。直接删枚举会让旧报告反序列化失败。

因此：**保留枚举成员**（向后兼容），但删掉打分分支里的特判，
并在枚举上加注释说明它没有对应 Source。同时在 `registry` 加一条断言型测试：
每个 `Platform` 成员要么有注册的 Source，要么在已知豁免名单里。
这样将来再加枚举而忘了实现，测试会失败。

## 验证策略

每个子任务的 gate 见 `implement.md`。整体验收靠 AC7：
**同口径重跑评测，与 baseline 对比**。这是本轮唯一能证明"改好了"的证据，
其余测试只能证明"改动符合意图"。
