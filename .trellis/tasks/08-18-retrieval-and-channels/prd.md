# 检索方式与取证渠道改造

## Goal

让 IdeaGo 的证据检索**问对问题、问对地方**，并且**能证明改好了**。

本轮不改报告契约、不改流水线结构、不新增数据源。只动「怎么问」和「怎么衡量问得好不好」。

## 前置决策（2026-08-18 用户确认）

| 决策 | 选择 | 影响 |
|---|---|---|
| 如何验证改进 | **跑真实 API 做前后对比** | 必须先建评测基线，否则无法证明召回变好 |
| 中文支持程度 | **中文能用就行，不新增中文渠道** | 把 `keywords_zh` 接进现有渠道的全部查询家族 |
| 渠道扩展 | **本轮不加新渠道** | 只清理幽灵渠道，把现有 6 源做对 |

## 现状证据（逐条查证，非推测）

### E1 中文关键词接进去了，但几乎没用

`keywords_zh` 在整个 `src/` 里只被消费**一次** —— `query_builder.py:332-334`，
只往 Tavily 的竞品家族插了**一条** `f"{zh_joined} 竞品"`。

其余全部是英文模板拼接：`f"{joined} alternative"` / `f"{joined} pain"` /
`f"switch from {kw}"` / `f"{joined} pricing"` / `f"{joined} recommend"`。

而 `llm/prompts/intent_parser.txt:7` 明确要求中文输入时产出 `keywords_zh`。
**抽出来了，然后基本丢掉。**

### E2 Reddit 的时效过滤被默认值中和掉了

先更正我此前的一个说法：Reddit **有** `sort=relevance` 也 **有** `t=` 时间过滤
（`reddit_source.py:282-283` OAuth 路径、`:358-359` 公共路径）。我之前说"没有"是错的。

真正的问题在映射函数 `_max_age_days_to_reddit_t`：

```
max_age_days= 90 -> t=year     ← 3 个月的意图变成 12 个月
max_age_days=180 -> t=year
max_age_days=365 -> t=year
max_age_days=730 -> t=all      ← 默认值，等于完全不过滤
```

`source_max_age_days` 默认就是 **730**，所以 **Reddit 的时效过滤在默认配置下是关闭的**。
而报告的第二段是 "Why Now"。

### E3 Reddit 没有 subreddit 定向

`restrict_sr` 在 `reddit_source.py` 里完全不存在；`subreddit` 只出现 1 次（`:222`），
是**读返回结果的字段**，不是构造查询。所有查询都是 Reddit 全局搜索。

痛点讨论集中在特定 sub，全局搜索 `"{keywords} pain"` 的前 10 条通常不是它们。

### E4 Reddit 当前跑在降级模式

本机 `.env`：`REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` 为空，
`REDDIT_ENABLE_PUBLIC_FALLBACK=true`。所以走公共只读回退：
`limit` 被压到 `reddit_public_fallback_limit`（默认 10，而 `max_results_per_source` 是 20），
且每次请求间有 1.5s 强制延迟，未认证的 Reddit 搜索也更容易被 429。

**这意味着基线测量必须在这个真实条件下做**，不能假装 OAuth 可用。

### E5 Tavily 是唯一的广度来源，用的却是最浅档位

```python
"search_depth": "basic"     # 未使用 advanced
# 无 include_domains / exclude_domains / topic
```

整条证据链的单点，既没提档也没做领域定向。

### E6 `GOOGLE_TRENDS` 是幽灵渠道

`Platform` 枚举声明了它，`pre_filter.py:135` 还专门给它写了打分分支
（`return OpportunityScoreBreakdown(score=0.5 if has_description else 0.1)`），
但**从未有 Source 实现、从未注册**。那段打分代码永远不会执行。

### E7 检索质量没有反馈闭环

`_SourceAdaptiveController`（`nodes.py:105`）只按**超时/失败率**降级，不看**结果相关性**。
`pre_filter` 算出的 opportunity score 只用于排序截断，**从不回流到 query planning**。
系统不知道自己问得好不好，下一次也不会问得更好。

## Requirements

### R1 先能测量，再谈改进

在改动任何检索逻辑之前，必须有一套**可重复运行、有记录**的召回评测：
固定的基准想法集（中英各若干）、跑真实 API、把结果落盘。
没有 baseline 的"改进"无法被证明，也无法被推翻。

### R2 中文想法要能用现有渠道拿到证据

`keywords_zh` 必须接进**全部**查询家族（痛点/替代/商业/迁移/工作流），
而不只是 Tavily 的竞品那一条。不新增中文渠道。

### R3 时效语义要自洽

"Why Now" 用的证据窗口不能等同于"竞品盘点"的窗口。至少要让
`source_max_age_days` 的意图不被 Reddit 的档位映射中和掉。

### R4 不得降低现有召回量

任何"更精准"的改动都可能把召回打薄。评测必须同时看**相关性**和**数量**，
出现召回塌陷要能立刻发现。

### R5 真实 API 调用要可控

评测会产生真实费用与配额消耗。必须支持限定跑哪些源、跑几个用例，
且默认不在 CI 里跑。

## Acceptance Criteria

- [ ] **AC1** 存在 `scripts/eval_retrieval.py`（或等价物），可重复运行，
      输出结构化结果到文件，支持 `--sources` / `--cases` / `--dry-run`
- [ ] **AC2** 有一份提交进仓的 baseline 结果（改造前，真实 API），
      含每个源每个查询家族的返回量与样本
- [ ] **AC3** 中文想法在**每一个**查询家族里都产出中文查询，有单元测试断言
- [ ] **AC4** Reddit 查询带 subreddit 定向；`t` 参数不再被默认值中和
- [ ] **AC5** Tavily 至少在关键家族上提档，且有领域定向策略
- [ ] **AC6** `GOOGLE_TRENDS` 幽灵渠道被清理（枚举、打分分支、相关测试一并处理）
- [ ] **AC7** 改造后重跑评测，与 baseline 同口径对比，
      **相关性有可见提升且召回量未塌陷**；结论写进任务产物
- [ ] **AC8** 全栈 gate 保持绿：ruff / format / mypy / pytest / 前端四件套
- [ ] **AC9** `.trellis/spec/` 记录检索层的新约定

## 非目标

- 不新增数据源（G2 / X / 知乎等留待后续，已单独记录）
- 不改报告契约与流水线节点结构
- 不做 pre_filter 分数回流 query planning 的反馈闭环 —— 见下

## 关于反馈闭环（E7）的处置

它是最有价值的一项，但**故意不放进本轮**：

在拿到 baseline 之前，无法判断简单修复（中文接入 + Reddit 定向 + Tavily 提档 +
时效修正）已经把差距补掉了多少。先量、先修显性问题、再量，然后由数据决定
闭环还值不值得建。先建闭环等于在没有度量的情况下调一个自适应系统。

## Constraints

- 分支 `saas`，base branch `saas`
- 评测默认不进 CI（真实 API 调用与费用）
- Reddit 在本机是公共降级模式，基线与验证都必须在此条件下进行并注明
- 不得为了"更精准"而牺牲召回量（R4）
