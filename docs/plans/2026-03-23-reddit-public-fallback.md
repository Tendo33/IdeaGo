# Reddit Public Fallback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 IdeaGo 的 Reddit 数据源增加公开只读 fallback，在没有 Reddit OAuth 凭证时仍可返回有限的公开讨论结果，并且不影响现有主流程与其他数据源。

**Architecture:** 维持现有 `RedditSource` 作为统一入口，在内部拆分出 `OAuth 搜索路径` 和 `公开只读搜索路径`。上层注册与 pipeline 不变，只扩展 source 内部策略、诊断信息和测试。公开只读路径仅支持搜索与基础字段映射，不承诺完整性，也不做写操作。

**Tech Stack:** Python 3.10+, `httpx`, `pytest`, `ruff`, `mypy`, Pydantic models, existing source error model

---

### Task 1: 明确 fallback 的行为契约

**Files:**
- Modify: `src/ideago/sources/reddit_source.py`
- Modify: `src/ideago/models/research.py`
- Test: `tests/test_sources.py`

**Step 1: 定义行为边界**

约定以下规则：

- 有 `client_id + client_secret` 时，默认走 OAuth
- 无凭证时，自动走 public fallback
- 有凭证但 token 申请失败时，不自动 fallback 到 public
- 有凭证但 OAuth 查询返回 `401/403`，不自动 fallback
- 有凭证但 OAuth 查询返回 `429`，不自动 fallback
- 仅在“无凭证”场景走 fallback，避免把认证问题伪装成正常结果

**Step 2: 在 `RawResult.raw_data` 中加入模式标记**

每条 Reddit 结果新增字段：

```python
{
    "auth_mode": "oauth" | "public_fallback"
}
```

可选再加：

```python
{
    "source_endpoint": "oauth_api" | "public_json"
}
```

**Step 3: 在 source 诊断信息中增加降级信息**

扩展 `consume_last_search_diagnostics()` 返回内容，增加：

```python
{
    "used_public_fallback": bool,
    "fallback_reason": str,
}
```

推荐 reason 值：

- `missing_credentials`
- `disabled_by_config`
- `none`

**Step 4: 写测试先约束契约**

新增测试点：

- 无凭证时 `search()` 不返回空，而是尝试 public fallback
- OAuth 模式成功时，结果 `raw_data["auth_mode"] == "oauth"`
- public fallback 成功时，结果 `raw_data["auth_mode"] == "public_fallback"`
- 有凭证但 token 失败时，仍抛错，不 silent fallback

**Step 5: 跑单测确认当前失败**

Run: `uv run pytest tests/test_sources.py -k reddit -v`

Expected:
- 新增 fallback 相关测试失败
- 现有 Reddit 测试保持可读，帮助我们以 TDD 方式推进

**Step 6: Commit**

```bash
git add tests/test_sources.py src/ideago/sources/reddit_source.py src/ideago/models/research.py
git commit -m "test: define reddit public fallback contract"
```

### Task 2: 在 RedditSource 内拆出双通道实现

**Files:**
- Modify: `src/ideago/sources/reddit_source.py`
- Test: `tests/test_sources.py`

**Step 1: 拆出内部私有方法，避免主函数膨胀**

推荐重构成这些内部方法：

- `_search_single_query_oauth(query: str, limit: int) -> list[RawResult]`
- `_search_single_query_public(query: str, limit: int) -> list[RawResult]`
- `_build_raw_result_from_reddit_post(post: dict, auth_mode: str) -> RawResult | None`
- `_should_use_public_fallback() -> tuple[bool, str]`

注意：

- 保持 `search()` 仍然是唯一外部入口
- 不新增新的 source 类，避免上层依赖注入复杂化

**Step 2: 公开只读 endpoint 设计**

优先使用：

- `https://www.reddit.com/search.json`

请求参数建议：

```python
{
    "q": query,
    "limit": min(limit, 10),
    "sort": "relevance",
    "t": "year",
    "type": "link",
}
```

限制建议：

- public fallback 单 query 最多 `10`
- 总并发强制降到 `1`
- query 间隔提高到 `1.5s - 2.0s`

**Step 3: 映射字段保持和 OAuth 版本一致**

保持至少这些字段：

- `title`
- `description`
- `url`
- `platform=Platform.REDDIT`
- `raw_data.post_id`
- `raw_data.subreddit`
- `raw_data.score`
- `raw_data.num_comments`
- `raw_data.created_utc`
- `raw_data.link_url`
- `raw_data.upvote_ratio`
- `raw_data.auth_mode`

如果 public JSON 某些字段缺失：

- 保持默认值
- 不抛错
- 不引入额外模型分支

**Step 4: 统一去重逻辑继续复用**

继续按 `post_id` 去重，不改上层逻辑。

**Step 5: 写最小实现后跑测试**

Run: `uv run pytest tests/test_sources.py -k "reddit and fallback" -v`

Expected:
- fallback 相关测试通过
- 旧 OAuth 测试仍通过

**Step 6: Commit**

```bash
git add src/ideago/sources/reddit_source.py tests/test_sources.py
git commit -m "feat: add public fallback for reddit source"
```

### Task 3: 增加配置开关和保护栏

**Files:**
- Modify: `src/ideago/config/settings.py`
- Modify: `src/ideago/api/dependencies.py`
- Modify: `src/ideago/sources/reddit_source.py`
- Test: `tests/test_sources.py`

**Step 1: 增加显式配置项**

建议新增设置：

- `reddit_enable_public_fallback: bool = True`
- `reddit_public_fallback_limit: int = 10`
- `reddit_public_fallback_delay_seconds: float = 1.5`

这样后续如果 Reddit 收紧策略，可以直接关掉 fallback。

**Step 2: 通过依赖注入把配置传进 RedditSource**

在注册 source 时传入这些参数，保持 source 自身不直接读全局 settings。

**Step 3: 限制 fallback 的触发条件**

仅允许：

- `not client_id or not client_secret`
- 且 `reddit_enable_public_fallback is True`

不允许在这些情况下 fallback：

- token 申请失败
- OAuth 查询 `401/403/429`
- 公开 fallback 本身出错后重试切回 OAuth

**Step 4: 写失败路径测试**

新增测试：

- 配置禁用 fallback 时，无凭证 `search()` 返回空
- 无凭证且 fallback 报错时，行为可控
- fallback 模式下 diagnostics 标记正确

**Step 5: 跑相关测试**

Run: `uv run pytest tests/test_sources.py -k reddit -v`

Expected:
- 配置与失败路径测试通过

**Step 6: Commit**

```bash
git add src/ideago/config/settings.py src/ideago/api/dependencies.py src/ideago/sources/reddit_source.py tests/test_sources.py
git commit -m "feat: add config guards for reddit public fallback"
```

### Task 4: 明确状态呈现，避免误导下游

**Files:**
- Modify: `src/ideago/sources/reddit_source.py`
- Modify: `src/ideago/pipeline/nodes.py`
- Test: `tests/test_sources.py`

**Step 1: 在 source diagnostics 中保留降级原因**

推荐结构：

```python
{
    "partial_failure": False,
    "failed_queries": [],
    "timed_out_queries": [],
    "used_public_fallback": True,
    "fallback_reason": "missing_credentials",
}
```

**Step 2: 在 pipeline 层评估是否要把 Reddit 标成 `DEGRADED`**

建议：

- OAuth 成功时，仍为 `OK`
- public fallback 成功时，Reddit 这个 source 标成 `DEGRADED`

这样前端和报告层就能分辨“拿到结果”和“高质量正常结果”不是一回事。

**Step 3: 若当前 nodes 已消费 diagnostics，就把 fallback 信息透传**

如果当前 source 结果汇总逻辑已经读取 diagnostics，就在那里把 `used_public_fallback=True` 转成 `SourceStatus.DEGRADED`。

**Step 4: 写一条回归测试**

验证：

- public fallback 有结果时，不应被当成 source failure
- 但 source status 不是普通 `OK`

**Step 5: Commit**

```bash
git add src/ideago/pipeline/nodes.py src/ideago/sources/reddit_source.py tests/test_sources.py
git commit -m "feat: mark reddit fallback results as degraded"
```

### Task 5: 文档与运维说明同步

**Files:**
- Modify: `AGENTS.md`
- Modify: `ai_docs/SETTINGS_GUIDE.md`
- Modify: `README.md`

**Step 1: 更新设置说明**

明确写出：

- Reddit OAuth 仍是首选方案
- 无凭证时可启用公开只读 fallback
- fallback 仅保证有限公开搜索能力
- fallback 结果可能不完整、可能受限流影响

**Step 2: 更新运行说明**

补充环境变量示例：

```env
REDDIT_CLIENT_ID=
REDDIT_CLIENT_SECRET=
REDDIT_ENABLE_PUBLIC_FALLBACK=true
REDDIT_PUBLIC_FALLBACK_LIMIT=10
REDDIT_PUBLIC_FALLBACK_DELAY_SECONDS=1.5
```

字段名最终以实际 settings 命名为准。

**Step 3: 不夸大能力**

文档里不要写“无需 Reddit app 即可正常支持 Reddit”，要写成：

- “在无法取得 OAuth 凭证时，可退化为公开只读抓取模式”

**Step 4: Commit**

```bash
git add ai_docs/SETTINGS_GUIDE.md AGENTS.md README.md
git commit -m "docs: document reddit public fallback behavior"
```

### Task 6: 全量验证与发布前检查

**Files:**
- No code changes required unless failures appear

**Step 1: 跑后端质量检查**

Run:

```bash
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
uv run mypy src
uv run pytest
```

Expected:
- 全部通过
- 若失败，优先修复 Reddit 相关受影响点，不顺手改 unrelated 逻辑

**Step 2: 人工验证场景**

至少验证这 4 组：

1. 有 Reddit 凭证
   预期：走 OAuth，`auth_mode=oauth`

2. 无 Reddit 凭证且 fallback 开启
   预期：返回有限结果，`auth_mode=public_fallback`

3. 无 Reddit 凭证且 fallback 关闭
   预期：Reddit source 返回空或不可用，但整体流程不崩

4. 有凭证但 token 失败
   预期：报错或按原有失败逻辑处理，不 silent fallback

**Step 3: 观察报告层表现**

检查最终报告中：

- Reddit 结果是否正常参与竞品提取
- source status 是否能反映 degraded
- 没有把 fallback 结果伪装成“完全可靠”

**Step 4: Commit**

```bash
git add .
git commit -m "feat: support public fallback for reddit source"
```
