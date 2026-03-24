# Frontend Audit Remediation Master Task

## 1. 背景

本任务基于 2026-03-24 对 IdeaGo 前端的整站审阅结果制定。  
目标不是做零散修补，而是用一轮有组织的 sub-agent 协作，把以下问题系统性收口：

- 前端页面与后端结果契约是否完全对应
- i18n 是否对齐、是否存在 fallback 漂移和硬编码英文
- landing / auth / legal / report / profile / history / admin 的体验是否一致
- 公共页和受保护页的无障碍、状态收尾、信息架构、source 口径是否合理
- 是否存在“代码看似支持，实际路由/行为未接通”的死功能
- 是否存在样式 token、motion 类名、平台类型等系统性漂移

## 2. 执行目标

本轮执行完成后，应满足以下目标：

1. 前端文案、状态、结构与后端 V2 决策优先报告合同一致。
2. 中英双语下不再出现明显的 fallback 英文、混合语言、错误 `lang` 属性。
3. landing、login、legal、report、profile、history 等关键页具备一致、可预测、可访问的交互。
4. source 数量与来源口径统一，不再出现 5 sources / 6 sources 冲突。
5. 取消分析、找不到报告、分析失败等终态有清晰 CTA。
6. pricing 页面如果存在实现，就必须在路由和入口上可达；如果不暴露，代码和文案也要收口。
7. motion、token、platform type、日期时间格式等系统问题完成归一化。
8. 最终通过 lint / typecheck / test / build，并进行一次复审。

## 3. 非目标

以下内容默认不在本轮范围内，除非任务中明确要求：

- 不改动产品核心业务定位
- 不新增新的报告 section
- 不修改后端检索/排序策略本身，除非为前后端合同对齐所必需
- 不做大规模视觉改版，不推翻现有 brutalist 方向
- 不引入新的 i18n 框架，不替换 React Router，不更换状态管理方案

## 4. 项目约束

执行时必须遵守：

- 先读 `ai_docs/AI_TOOLING_STANDARDS.md`
- 前端规则以 `ai_docs/FRONTEND_STANDARDS.md` 为准
- 前后端合同变更必须前后一起收口
- 优先更新现有文件，不随意扩展新抽象
- 每个任务尽量小而封闭，可独立 review
- 使用 sub-agent 执行时，严格避免重叠写文件
- 所有任务都必须有 skill 显式绑定
- 所有完成声明都必须有验证证据

## 5. 执行模式

本任务采用“主控 agent + sub-agent 工作包”模式执行。

规则：

1. 一个任务只分配给一个 worker。
2. 一个 worker 只负责自己任务声明的文件和行为范围。
3. 不允许不同 worker 同时编辑相同文件。
4. 主控 agent 负责：
   - 派工
   - 合并结果
   - 跑统一验证
   - 组织最终 audit
5. 每个 worker 完成后必须返回：
   - 修改摘要
   - 影响文件
   - 风险点
   - 已执行验证
6. 每一波任务结束后再进入下一波，除非明确标记为可并行。

## 6. 全局验收标准

全局完成标准：

- `pnpm --prefix frontend lint` 通过
- `pnpm --prefix frontend typecheck` 通过
- `pnpm --prefix frontend test` 通过
- `pnpm --prefix frontend build` 通过
- 关键页面在 `390px` 和 `1440px` 下无明显回归
- 中英切换后：
  - `document.documentElement.lang` 正确
  - 页面标题正确
  - 主要文案不混用中英 fallback
  - 日期时间格式与语言一致
- landing / login / legal / report / history / profile / admin 无重大 a11y 问题
- 后端结果与前端字段语义一致
- 不再出现 source 数量或来源口径冲突

## 7. 任务分波次

### Wave 1：公共壳层、i18n 基础、source truth、入口信息架构

这波优先处理“全局会继续污染所有页面”的基础问题。

#### Task 1: 公共壳层语言与可访问性修复

- Sub-agent: `worker-public-shell-a11y`
- Skill: `harden`
- 目标：
  - 修复 `document.documentElement.lang` 仅在登录后才更新的问题
  - 修复语言切换按钮的 aria 文案硬编码
  - 统一公共页和登录后页面的语言状态同步
  - 修复 `Link > Button` 语义嵌套问题
- 主要范围：
  - `frontend/src/app/App.tsx`
  - `frontend/src/features/landing/LandingPage.tsx`
  - `frontend/src/features/auth/AuthCallback.tsx`
  - `frontend/src/lib/auth/ProtectedRoute.tsx`
- 必做结果：
  - 未登录页面也正确设置 `lang`
  - 不再出现无效交互嵌套
  - 关键按钮具备正确可访问名称
- 禁止：
  - 不改 landing 视觉方向
  - 不改 auth 业务流程
- 验收：
  - Playwright 检查 `/`、`/login`、`/terms`
  - 中英切换后 `lang` 正确
  - 键盘可达

#### Task 2: Locale 基础补齐

- Sub-agent: `worker-locale-foundation`
- Skill: `clarify`
- 目标：
  - 补齐当前代码已引用但缺失的 key
  - 清理关键 fallback 漂移
  - 保证 `en` / `zh` 资源结构对称
- 主要范围：
  - `frontend/src/lib/i18n/locales/en/translation.json`
  - `frontend/src/lib/i18n/locales/zh/translation.json`
- 必补 key 范围：
  - `legal.*`
  - `auth.legalNotice`
  - `common.and`
  - `history.deleted`
  - `pricing.loadError`
  - `pricing.upgradeError`
  - `pricing.signInToUpgrade`
  - `profile.dangerZone`
  - `profile.deleteWarning`
  - `profile.deleteAccount`
  - `profile.deleteConfirm`
  - `profile.deleteError`
  - `profile.confirmDelete`
  - `profile.cancelDelete`
  - `report.analyzing`
  - `report.sections.shouldWeBuildThis`
  - `report.sections.whyNow`
  - `report.sections.pain`
  - `report.sections.whitespace`
  - `report.sections.evidenceConfidence`
  - `report.sections.painPlaceholder`
  - `report.sections.whitespacePlaceholder`
- 验收：
  - 代码引用 key 与 locale 文件一致
  - 不再依赖 inline 英文 fallback 作为主路径

#### Task 3: Source 口径统一

- Sub-agent: `worker-source-truth`
- Skill: `clarify`
- 目标：
  - 统一 landing、pricing、home、report 文案中的 source 数量和来源集合
  - 明确当前固定 source set 为 6 个
- 主要范围：
  - `frontend/src/features/landing/LandingPage.tsx`
  - `frontend/src/features/home/HomePage.tsx`
  - 两份 locale JSON
- 必做结果：
  - 不再出现 `5 platforms` / `6 data sources` 冲突
  - 文案与后端实际固定来源一致
- 参考真相：
  - `src/ideago/models/research.py`
  - `src/ideago/api/dependencies.py`
- 验收：
  - 审阅页面所有 source 文案一致
  - landing 与 pricing 不互相打架

#### Task 4: Pricing 暴露与入口打通

- Sub-agent: `worker-billing-entry`
- Skill: `onboard`
- 目标：
  - 如果 `PricingPage` 已存在且有业务意义，则路由必须可达
  - 为用户提供一致、明确的升级入口
- 主要范围：
  - `frontend/src/app/App.tsx`
  - `frontend/src/features/pricing/PricingPage.tsx`
  - `frontend/src/features/auth/components/UserMenu.tsx`
  - 必要时首页/个人页入口
- 决策默认值：
  - 默认新增 `/pricing` 路由
  - 默认从用户菜单或 profile 提供入口
- 验收：
  - `/pricing` 可访问
  - 未登录与已登录状态下升级路径一致
  - 无死页面

### Wave 2：报告页 V2 文案与状态收尾

#### Task 5: 报告页核心文案全量 i18n 化

- Sub-agent: `worker-report-copy-v2`
- Skill: `clarify`
- 目标：
  - 清除报告页核心硬编码英文
  - 保证后端 `output_language` 与前端外层 chrome 语言一致
- 主要范围：
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - `frontend/src/features/reports/components/PainSignalsCard.tsx`
  - `frontend/src/features/reports/components/CommercialSignalsCard.tsx`
  - `frontend/src/features/reports/components/ConfidenceCard.tsx`
  - `frontend/src/features/reports/components/MarketOverview.tsx`
  - `frontend/src/features/reports/components/WhitespaceOpportunityCard.tsx`
  - `frontend/src/features/reports/components/InsightCard.tsx`
  - `frontend/src/features/reports/components/ReportContentPane.tsx`
- 必做结果：
  - 所有 section label、badge、说明、fallback 文案进入 locale
  - 中文报告 UI 不再被英文 chrome 包住
- 验收：
  - 中文环境下报告页主结构无硬编码英文
  - 英文环境下语义自然，不是直译痕迹

#### Task 6: 报告生命周期终态修复

- Sub-agent: `worker-report-lifecycle`
- Skill: `harden`
- 目标：
  - 收口 cancelled、missing、failed、processing-complete-but-unavailable 等终态
  - 确保每个终态都有清晰 CTA
- 主要范围：
  - `frontend/src/features/reports/components/useReportLifecycle.ts`
  - `frontend/src/features/reports/ReportPage.tsx`
  - `frontend/src/features/reports/components/ReportProgressPane.tsx`
  - 必要时 `ReportErrorBanner`
- 必做结果：
  - cancelled 后不出现“结束了但没下一步”
  - 失败/取消/找不到都能明确恢复或返回
- 验收：
  - 手动模拟 cancelled / missing / failed 场景
  - 无死路状态

#### Task 7: 后端状态合同收敛

- Sub-agent: `worker-report-contract-backend`
- Skill: `backend-engineering-playbook`
- 目标：
  - 明确 `/reports/{id}/status` 对 truly missing ID 的合同
  - 与前端统一，不允许“前端等 typed status，后端先抛 404”这种分裂语义
- 主要范围：
  - `src/ideago/api/routes/reports.py`
  - 必要时 `src/ideago/api/schemas.py`
  - 前端调用方若受影响则同步
- 默认决策：
  - 以“单一语义”为准，不允许前后端各自猜
  - 若保留 typed `not_found`，前后端都按此处理
  - 若采用 HTTP 404，则前端也按 HTTP 404 作为正式路径
- 验收：
  - 行为文档清晰
  - 前端终态逻辑与后端实际返回一致

#### Task 8: SSE 数据边界硬化

- Sub-agent: `worker-sse-contract`
- Skill: `harden`
- 目标：
  - 把匿名 `Record<string, unknown>` 驱动的 progress UI 收敛为更稳定的类型边界
  - 至少避免静默字段漂移
- 主要范围：
  - `frontend/src/lib/types/research.ts`
  - `frontend/src/lib/api/useSSE.ts`
  - `frontend/src/features/reports/components/ReportProgressPane.tsx`
  - 必要时后端事件侧
- 默认决策：
  - 不要求一次性引入复杂 schema 框架
  - 但必须建立最小类型合同与容错分支
- 验收：
  - progress UI 对缺字段/变字段不 silently break
  - 关键字段有显式解析逻辑

### Wave 3：类型、格式、token、motion 归一化

#### Task 9: Platform 类型收口

- Sub-agent: `worker-platform-contract`
- Skill: `normalize`
- 目标：
  - 移除前端过期平台类型
  - 保证 platform 枚举只表达当前正式合同
- 主要范围：
  - `frontend/src/lib/types/research.ts`
  - `frontend/src/features/reports/components/*`
  - `frontend/src/features/home/components/*`
- 必做结果：
  - 删除 stale `google_trends`
  - 所有 platform 显示逻辑与后端一致
- 验收：
  - TS 类型闭合
  - 无孤立平台分支

#### Task 10: 日期时间格式随语言走

- Sub-agent: `worker-locale-formatting`
- Skill: `normalize`
- 目标：
  - 统一日期时间格式策略
  - 让格式跟 app 当前语言，而不是浏览器默认 locale
- 主要范围：
  - `frontend/src/features/home/HomePage.tsx`
  - `frontend/src/features/history/HistoryPage.tsx`
  - `frontend/src/features/profile/ProfilePage.tsx`
  - `frontend/src/features/admin/AdminPage.tsx`
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - 必要时抽一个轻量 formatter
- 默认决策：
  - 允许新增小型 util
  - 不引入重型日期库
- 验收：
  - zh 下中文日期格式
  - en 下英文日期格式
  - 同页不再混乱

#### Task 11: Token 和颜色归一化

- Sub-agent: `worker-token-cleanup`
- Skill: `normalize`
- 目标：
  - 清理少量裸 palette
  - 尽量通过现有 token 体系表达颜色
- 主要范围：
  - `frontend/src/features/reports/components/PlatformIcons.tsx`
  - `frontend/src/features/reports/components/InsightCard.tsx`
- 必做结果：
  - 减少 `orange-500` / `emerald-500` 这类孤岛色
  - 保持现有视觉方向，不做重设计
- 验收：
  - 颜色语义更一致
  - 明暗主题下不出意外冲突

#### Task 12: Motion 类名与实际产物对齐

- Sub-agent: `worker-motion-cleanup`
- Skill: `distill`
- 目标：
  - 清理当前代码里看似存在、实际产物里无效的 easing / animation 类
  - 用真实有效的 motion 方案替换
- 主要范围：
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - `frontend/src/features/reports/components/ConfidenceCard.tsx`
  - `frontend/src/features/reports/components/ReportContentPane.tsx`
  - 其他包含 `ease-out-quint` / `ease-out-quart` / `ease-out-expo` / `animate-in` 的组件
- 默认决策：
  - 优先使用真实 Tailwind 可用类或现有 CSS
  - 不引入额外 motion 依赖
- 验收：
  - 代码里的 motion 声明真实生效
  - 无伪动画类残留

### Wave 4：输入 guardrail、法务与共享层收尾、最终复审

#### Task 13: 搜索输入 guardrail 对齐后端

- Sub-agent: `worker-input-guardrails`
- Skill: `harden`
- 目标：
  - 让前端在提交前尽量拦住后端必拒的无效输入
  - 减少无意义请求和错误提示延迟
- 主要范围：
  - `frontend/src/features/home/components/SearchBox.tsx`
  - `frontend/src/features/home/HomePage.tsx`
  - 对照 `src/ideago/api/schemas.py`
- 默认决策：
  - 不复制全部后端逻辑细节
  - 但至少覆盖：字母缺失、语义过弱、符号比例异常
- 验收：
  - 明显垃圾输入前端直接提示
  - 正常输入无误伤

#### Task 14: Legal 与共享辅助文案收尾

- Sub-agent: `worker-shared-copy-a11y`
- Skill: `clarify`
- 目标：
  - 补齐 admin / accessibility / source error / shared helper 的英文硬编码
- 主要范围：
  - `frontend/src/features/admin/AdminPage.tsx`
  - `frontend/src/lib/utils/sourceErrorMessage.ts`
  - `frontend/src/features/reports/components/RelevanceRing.tsx`
  - 必要时 `UserMenu`、`App.tsx`
- 验收：
  - 共享层文本不再偷跑英文
  - aria 文案和错误提示可本地化

#### Task 15: 最终质量打磨

- Sub-agent: `worker-final-polish`
- Skill: `polish`
- 目标：
  - 收最后一轮视觉/文案/交互细节不一致
  - 确保页面在主要断点下无明显粗糙感
- 范围：
  - 只允许修轻量一致性问题
  - 不得引入新功能
- 验收：
  - 视觉/文案/按钮层级一致
  - 无明显页面碎裂感

#### Task 16: 最终复审

- Sub-agent: `worker-regression-audit`
- Skill: `audit`
- 目标：
  - 对改动后的全站做一次复审
  - 输出剩余问题和 residual risk
- 覆盖页面：
  - `/`
  - `/login`
  - `/terms`
  - `/privacy`
  - `/reports`
  - `/reports/:id`
  - `/profile`
  - `/admin`
  - `/pricing`
- 覆盖视口：
  - `390x844`
  - `1440x1100`
- 复审重点：
  - i18n 是否已对齐
  - a11y 是否显著改善
  - 后端结果合同是否对应
  - landing / pricing / report 口径是否统一
- 输出：
  - 剩余问题
  - 风险等级
  - 是否建议收尾上线

## 8. 并行策略

### 可并行波次

#### Wave 1 可并行

- Task 1
- Task 2
- Task 3
- Task 4

说明：

- Task 2 只改 locale 文件
- Task 3 主要改营销/文案面
- Task 1 改公共壳层
- Task 4 改 routing / entry
- 主控需先分清文件 ownership，防止 `LandingPage.tsx` 重叠编辑
- 如果 Task 1 与 Task 3 都要改 `LandingPage.tsx`，则必须串行：
  - 先 Task 1
  - 后 Task 3

#### Wave 2 可并行

- Task 5
- Task 6
- Task 7
- Task 8

说明：

- Task 5 与 Task 6 可能都碰 report 相关文件，默认串行：
  - 先 Task 6 解决状态流
  - 后 Task 5 收文案
- Task 7 后端可并行
- Task 8 需避开与 Task 6 的同文件冲突

#### Wave 3 可并行

- Task 9
- Task 10
- Task 11
- Task 12

说明：

- 这些任务系统性强，但文件交叉较少
- 若 Task 10 需要抽 util，则主控先确认新 util 放置位置

#### Wave 4 串行

- Task 13
- Task 14
- Task 15
- Task 16

说明：

- Wave 4 主要用于收尾与回归，不建议再大并行

## 9. 每个 worker 的输出格式

每个 sub-agent 完成任务后，必须返回以下内容：

1. 完成摘要
2. 实际修改文件
3. 关键行为变化
4. 风险和兼容性说明
5. 执行过的验证命令
6. 是否存在需要主控补合并的冲突点

## 10. Review Gate

每个任务完成后必须经过两层 review：

### 1. Spec Review

- 是否完成任务目标
- 是否越界实现
- 是否遗漏验收标准

### 2. Quality Review

- 是否符合项目代码风格
- 是否引入脆弱逻辑
- 是否有 i18n / a11y / typing 回退
- 是否破坏前后端合同

任何 review 未通过，不得进入下一波。

## 11. 验证命令

### 前端统一验证

```bash
pnpm --prefix frontend lint
pnpm --prefix frontend typecheck
pnpm --prefix frontend test
pnpm --prefix frontend build
```

### 浏览器复查建议

- 检查中英切换后的 `lang`
- 检查移动端 `390px` 是否无横向滚动
- 检查 `/pricing` 是否真实可达
- 检查 report 终态：
  - processing
  - failed
  - cancelled
  - missing
  - ready
- 检查 legal 页是否仍有英文 fallback
- 检查 source 数量与来源口径是否一致

## 12. 关键风险

- locale 文件与代码引用继续漂移
- 多个 worker 同时编辑 report 组件导致冲突
- 状态流修复后破坏已有测试
- pricing 路由接通后暴露出 billing 端额外问题
- 后端 `/status` 合同若未统一，前端永远有一条死分支
- 收 token / motion 时误伤现有视觉风格

## 13. 明确默认决策

除非主控另行修改，本任务默认采用以下决策：

- `task.md` 使用中文
- 文件放仓库根目录
- source truth 按 6 个固定来源写
- `/pricing` 默认接入路由
- 时间格式跟 app 当前语言走
- 报告页所有硬编码英文默认全部移入 locale
- `google_trends` 视为 stale 类型，默认移除
- 终态 UI 默认必须有 CTA
- 复审必须使用 `audit`
- 所有执行任务必须使用这里声明的 skill，不允许临场换成无关 skill

## 14. 完成定义

本总任务完成的标志是：

- 所有任务通过 review gate
- 前端验证命令全部通过
- 最终 audit 无 high 级残留问题
- 前后端合同、i18n、入口信息架构、终态体验已收口
- `task.md` 自身可作为后续执行记录和复盘依据

## 15. 文档自检清单

主控在正式按本任务派工前，应先完成一次非变更检查，确认任务书本身可执行：

- 检查所有 skill 名称都来自当前可用 skills 列表
- 检查所有任务不存在明显重叠写集
- 检查所有任务都有验收标准
- 检查所有引用路径都存在
- 检查波次排序不会出现先后矛盾
- 检查全局验证命令与 `AGENTS.md` 一致

## 16. 使用假设

- 默认新文件名就是 `task.md`，放仓库根目录
- 默认文档语言使用中文
- 默认这是一份“可直接交给后续 agent 执行的任务书”，不是简版摘要
- 默认保留本轮审阅给出的 skill 映射，不再重新发明新的 skill 组合
- 默认主控会按本文档的波次、ownership 和 review gate 执行，而不是并发乱派工

## 17. 执行摘要

本任务按“主控 agent + 每 task 一名 implementer + 两级 reviewer”执行。

执行单位不是“一个 task = 一个 agent 完成全部工作”，而是：

- `implementer` sub-agent：负责实现具体 task
- `spec-reviewer` sub-agent：只检查是否满足本文档定义的目标、范围、禁止事项和验收标准
- `quality-reviewer` sub-agent：只检查代码质量、合同一致性、i18n / a11y / typing 回归风险

主控 agent 负责：

- 按波次派工
- 控制并行边界
- 避免写集冲突
- 汇总 review 结果
- 每波跑统一验证
- 在全部完成后组织最终 audit

## 18. 执行规则

### 18.1 Task 固定生命周期

每个 task 必须按以下顺序完成：

1. 主控准备该 task 的完整上下文
2. 派发 implementer sub-agent
3. implementer 实现、自检并回报
4. 派发 `spec-review::<task-id>`
5. 若 spec-review 未通过，回 implementer 修复并重新 spec-review
6. spec-review 通过后，派发 `quality-review::<task-id>`
7. 若 quality-review 未通过，回 implementer 修复并重新 quality-review
8. 两级 review 都通过后，主控将该 task 标记为完成

### 18.2 Implementer Prompt 必填项

每个 implementer prompt 必须包含：

- task 目标
- 允许修改的文件范围
- 禁止事项
- 依赖的上游 task
- 验收标准
- 必跑验证
- 与其他 task 的写集冲突提醒

### 18.3 并行约束

- 不允许两个 implementer 同时编辑同一文件
- 不允许 implementer 和 implementer 在共享 write set 上并行
- reviewer 原则上只读，可与其他 reviewer 并行
- 每波结束后必须先完成统一验证，再进入下一波

### 18.4 锁定公共合同

执行过程中，以下内容视为显式合同，不得临场改口：

- 报告 UI 必须与后端 V2 decision-first 合同一致
- 固定 source truth 只包含：`github`、`tavily`、`hackernews`、`appstore`、`producthunt`、`reddit`
- 前端 `Platform` 类型必须与后端模型收敛，移除 `google_trends`
- `/pricing` 默认正式暴露并接通入口
- `/reports/{id}/status` 缺失态语义必须前后端统一
- `document.documentElement.lang`、日期格式、aria 文案、页面标题都属于产品合同

## 19. 执行任务矩阵

### Wave 1 执行矩阵

#### task-1

- Worker: `worker-public-shell-a11y`
- Skill: `harden`
- Agent chain:
  - `implementer::task-1`
  - `spec-review::task-1`
  - `quality-review::task-1`
- Start condition: 无
- Write set:
  - `frontend/src/app/App.tsx`
  - `frontend/src/features/landing/LandingPage.tsx`
  - `frontend/src/features/auth/AuthCallback.tsx`
  - `frontend/src/lib/auth/ProtectedRoute.tsx`
- Finish condition:
  - 未登录页面正确同步 `lang`
  - 语言切换 aria 文案不再硬编码
  - `Link > Button` 嵌套被清理

#### task-2

- Worker: `worker-locale-foundation`
- Skill: `clarify`
- Agent chain:
  - `implementer::task-2`
  - `spec-review::task-2`
  - `quality-review::task-2`
- Start condition: 无
- Write set:
  - `frontend/src/lib/i18n/locales/en/translation.json`
  - `frontend/src/lib/i18n/locales/zh/translation.json`
- Finish condition:
  - task.md 中列出的缺失 key 全补齐
  - `en` 与 `zh` 结构对称
  - 不新增无用 key

#### task-3

- Worker: `worker-source-truth`
- Skill: `clarify`
- Agent chain:
  - `implementer::task-3`
  - `spec-review::task-3`
  - `quality-review::task-3`
- Start condition: `task-1` 完成
- Write set:
  - `frontend/src/features/landing/LandingPage.tsx`
  - `frontend/src/features/home/HomePage.tsx`
  - locale JSON
- Finish condition:
  - 页面不再同时出现 `5 platforms` 与 `6 data sources`
  - 文案与后端 6 个固定来源一致

#### task-4

- Worker: `worker-billing-entry`
- Skill: `onboard`
- Agent chain:
  - `implementer::task-4`
  - `spec-review::task-4`
  - `quality-review::task-4`
- Start condition: `task-1` 完成
- Write set:
  - `frontend/src/app/App.tsx`
  - `frontend/src/features/pricing/PricingPage.tsx`
  - `frontend/src/features/auth/components/UserMenu.tsx`
  - 必要时 profile 入口相关文件
- Finish condition:
  - `/pricing` 可访问
  - 升级入口不再是死链或隐藏功能

### Wave 2 执行矩阵

#### task-6

- Worker: `worker-report-lifecycle`
- Skill: `harden`
- Agent chain:
  - `implementer::task-6`
  - `spec-review::task-6`
  - `quality-review::task-6`
- Start condition: `task-2` 完成
- Write set:
  - `frontend/src/features/reports/components/useReportLifecycle.ts`
  - `frontend/src/features/reports/ReportPage.tsx`
  - `frontend/src/features/reports/components/ReportProgressPane.tsx`
  - 必要时 `ReportErrorBanner`
- Finish condition:
  - `cancelled / failed / missing / complete-but-unavailable` 都有明确终态与 CTA

#### task-7

- Worker: `worker-report-contract-backend`
- Skill: `backend-engineering-playbook`
- Agent chain:
  - `implementer::task-7`
  - `spec-review::task-7`
  - `quality-review::task-7`
- Start condition: 无
- Write set:
  - `src/ideago/api/routes/reports.py`
  - 必要时 `src/ideago/api/schemas.py`
  - 若合同受影响，再同步前端最小调用面
- Finish condition:
  - `/reports/{id}/status` 缺失态语义被正式收敛

#### task-8

- Worker: `worker-sse-contract`
- Skill: `harden`
- Agent chain:
  - `implementer::task-8`
  - `spec-review::task-8`
  - `quality-review::task-8`
- Start condition: `task-6` 完成
- Write set:
  - `frontend/src/lib/types/research.ts`
  - `frontend/src/lib/api/useSSE.ts`
  - `frontend/src/features/reports/components/ReportProgressPane.tsx`
  - 必要时后端事件相关文件
- Finish condition:
  - progress UI 具备最小稳定类型边界
  - 缺字段或变字段时不 silently break

#### task-5

- Worker: `worker-report-copy-v2`
- Skill: `clarify`
- Agent chain:
  - `implementer::task-5`
  - `spec-review::task-5`
  - `quality-review::task-5`
- Start condition:
  - `task-2` 完成
  - `task-6` 完成
- Write set:
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - `frontend/src/features/reports/components/PainSignalsCard.tsx`
  - `frontend/src/features/reports/components/CommercialSignalsCard.tsx`
  - `frontend/src/features/reports/components/ConfidenceCard.tsx`
  - `frontend/src/features/reports/components/MarketOverview.tsx`
  - `frontend/src/features/reports/components/WhitespaceOpportunityCard.tsx`
  - `frontend/src/features/reports/components/InsightCard.tsx`
  - `frontend/src/features/reports/components/ReportContentPane.tsx`
  - locale JSON
- Finish condition:
  - 中文报告 UI 无核心硬编码英文
  - 外层 chrome 与 `output_language` 一致

### Wave 3 执行矩阵

#### task-9

- Worker: `worker-platform-contract`
- Skill: `normalize`
- Agent chain:
  - `implementer::task-9`
  - `spec-review::task-9`
  - `quality-review::task-9`
- Start condition:
  - `task-7` 完成
  - `task-8` 完成
- Write set:
  - `frontend/src/lib/types/research.ts`
  - platform 相关展示组件
- Finish condition:
  - `google_trends` 被移除
  - 平台枚举与后端一致

#### task-10

- Worker: `worker-locale-formatting`
- Skill: `normalize`
- Agent chain:
  - `implementer::task-10`
  - `spec-review::task-10`
  - `quality-review::task-10`
- Start condition: `task-5` 完成
- Write set:
  - `frontend/src/features/home/HomePage.tsx`
  - `frontend/src/features/history/HistoryPage.tsx`
  - `frontend/src/features/profile/ProfilePage.tsx`
  - `frontend/src/features/admin/AdminPage.tsx`
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - 必要时新增轻量 formatter util
- Finish condition:
  - 日期时间格式跟 app 当前语言走

#### task-11

- Worker: `worker-token-cleanup`
- Skill: `normalize`
- Agent chain:
  - `implementer::task-11`
  - `spec-review::task-11`
  - `quality-review::task-11`
- Start condition: `task-5` 完成
- Write set:
  - `frontend/src/features/reports/components/PlatformIcons.tsx`
  - `frontend/src/features/reports/components/InsightCard.tsx`
  - 必要时全局 token 文件
- Finish condition:
  - 颜色回到现有 token 体系
  - 不再残留明显孤岛色

#### task-12

- Worker: `worker-motion-cleanup`
- Skill: `distill`
- Agent chain:
  - `implementer::task-12`
  - `spec-review::task-12`
  - `quality-review::task-12`
- Start condition: `task-5` 完成
- Write set:
  - `frontend/src/features/reports/components/ReportHeader.tsx`
  - `frontend/src/features/reports/components/ConfidenceCard.tsx`
  - `frontend/src/features/reports/components/ReportContentPane.tsx`
  - 其他假 easing / 假动画类所在组件
- Finish condition:
  - 无效 motion 类被移除
  - 实际产物中动画声明真实生效

### Wave 4 执行矩阵

#### task-13

- Worker: `worker-input-guardrails`
- Skill: `harden`
- Agent chain:
  - `implementer::task-13`
  - `spec-review::task-13`
  - `quality-review::task-13`
- Start condition: `task-2` 完成
- Write set:
  - `frontend/src/features/home/components/SearchBox.tsx`
  - `frontend/src/features/home/HomePage.tsx`
- Finish condition:
  - 明显垃圾输入前端直接提示
  - 正常输入不误伤

#### task-14

- Worker: `worker-shared-copy-a11y`
- Skill: `clarify`
- Agent chain:
  - `implementer::task-14`
  - `spec-review::task-14`
  - `quality-review::task-14`
- Start condition: `task-2` 完成
- Write set:
  - `frontend/src/features/admin/AdminPage.tsx`
  - `frontend/src/lib/utils/sourceErrorMessage.ts`
  - `frontend/src/features/reports/components/RelevanceRing.tsx`
  - 必要时 `UserMenu`、`App.tsx`
  - locale JSON
- Finish condition:
  - 共享层文案和 aria 文案可本地化
  - 中英切换无偷跑英文

#### task-15

- Worker: `worker-final-polish`
- Skill: `polish`
- Agent chain:
  - `implementer::task-15`
  - `spec-review::task-15`
  - `quality-review::task-15`
- Start condition:
  - `task-10` 完成
  - `task-11` 完成
  - `task-12` 完成
  - `task-13` 完成
  - `task-14` 完成
- Write set:
  - 只允许修轻量一致性问题
- Finish condition:
  - 页面在主要断点下无明显碎裂感

#### task-16

- Worker: `worker-regression-audit`
- Skill: `audit`
- Agent chain:
  - `implementer::task-16`
- Start condition: Wave 1-4 全部完成
- Write set:
  - 无，原则上只读
- Finish condition:
  - 输出最终残留问题、风险等级、是否建议收尾上线

## 20. 波次执行顺序

### Wave 1

执行顺序：

1. `task-1`
2. 并行：`task-2`
3. `task-1` 完成后，并行：`task-3`、`task-4`
4. Wave 1 统一验证

### Wave 2

执行顺序：

1. `task-6`
2. 可并行：`task-7`
3. `task-6` 完成后：`task-8`
4. `task-2` 与 `task-6` 完成后：`task-5`
5. Wave 2 统一验证

### Wave 3

执行顺序：

1. `task-9`
2. `task-5` 完成后，并行：`task-11`、`task-12`
3. `task-5` 完成后：`task-10`
4. Wave 3 统一验证

### Wave 4

执行顺序：

1. 并行：`task-13`、`task-14`
2. 之后：`task-15`
3. 最后：`task-16`
4. Wave 4 统一验证

## 21. Review Todo

每个 task 固定生成以下 review todo：

- `spec-review::<task-id>`
- `quality-review::<task-id>`

Reviewer 的职责边界：

- `spec-review`
  - 只看是否满足目标、范围、禁止事项、验收标准
  - 不做风格建议扩张
- `quality-review`
  - 只看 typing、i18n、a11y、contract、一致性、回归风险
  - 不再重复 spec-review 结论，除非该问题影响质量

任何 reviewer 未通过，该 task 不得进入下一波。

## 22. Controller Todo List

主控的大 todo 固定如下：

1. 读取 `task.md` 并抽取 16 个 task 的完整上下文
2. 为每个 task 建立：
   - `task id`
   - `wave`
   - `skill`
   - `write set`
   - `deps`
   - `acceptance`
   - `verification`
3. 按波次派发 implementer
4. implementer 完成后启动 `spec-review`
5. spec-review 通过后启动 `quality-review`
6. 任一 review 不通过则回 implementer 修复并复审
7. 每波完成后统一跑：
   - `pnpm --prefix frontend lint`
   - `pnpm --prefix frontend typecheck`
   - `pnpm --prefix frontend test`
   - `pnpm --prefix frontend build`
8. 全部通过后启动 `worker-regression-audit`
9. 根据最终 audit 结果决定：
   - 无 high 残留：收尾
   - 有 high 残留：回到对应 task 或新建补丁 task

## 23. 执行阶段测试计划

- 每波结束跑一次四项前端验证
- 至少一次真实浏览器检查：
  - 中英切换后的 `lang`
  - `/pricing` 可达性
  - `390px` 无横向滚动
  - report 五种终态：`processing / failed / cancelled / missing / ready`
- 最终 audit 必须覆盖：
  - landing
  - auth
  - legal
  - report
  - profile
  - history
  - admin
  - pricing
  - 视口 `390x844` 和 `1440x1100`

## 24. 执行假设

- 使用 `subagent-driven-development` 作为单 task 交付规范
- 使用 `dispatching-parallel-agents` 只在写集不冲突时并行
- `/pricing` 默认正式暴露
- `google_trends` 默认视为 stale，必须移除
- 执行阶段不修改产品定位，不新增新的报告 section，不做大规模重设计
