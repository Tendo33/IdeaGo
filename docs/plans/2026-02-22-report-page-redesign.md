# IdeaGo Report Page Redesign — 详细改进方案

> 产品设计 + UI/UX 改进建议，不涉及代码更改

---

## 一、现状诊断：用户旅程全链路审计

### 当前流程

```
HomePage (输入 idea)
    ↓  POST /analyze → navigate to /reports/{id}
ReportPage — Phase 1: Progress (等待 20-30s)
    │  SSE events 驱动竖向时间线
    │  7 个步骤逐个 pending → active → done
    │  用户完全被动等待
    ↓  isComplete = true
ReportPage — Phase 2: Report (硬切换)
    │  ProgressTracker 消失
    │  report 以 fade-in 出现
    │  线性堆叠: SourceStatusBar → ReportSummary → RelevanceChart → CompetitorCards
    ↓
    用户向下滚动阅读
```

### 五个核心痛点

| # | 痛点 | 严重度 | 描述 |
|---|------|--------|------|
| 1 | **死亡等待** | 高 | 20-30 秒的进度页面是纯被动观看，用户焦虑感最强的时刻却没有任何有价值的内容 |
| 2 | **硬状态切换** | 中 | Progress → Report 是二元跳变，进度追踪器突然消失，报告突然出现，缺乏叙事连续性 |
| 3 | **扁平信息层级** | 高 | 推荐结论、市场概览、竞品列表的视觉权重几乎相同，用户无法"一眼"获取核心判断 |
| 4 | **单一消费模式** | 中 | 报告只能线性滚动阅读，没有对比、标注、筛选深度交互，信息利用率低 |
| 5 | **无叙事弧线** | 中 | 数据平铺直叙，缺少"结论 → 证据 → 行动"的决策引导结构 |

---

## 二、设计理念：从"静态报告"到"渐进式分析仪表盘"

### 核心原则

1. **Progressive Disclosure（渐进展示）**：数据到一块展示一块，不让用户干等
2. **Narrative Arc（叙事弧线）**：引导用户从"结论"到"证据"到"行动"
3. **Information Density（信息密度）**：关键数据一屏可见，细节按需展开
4. **Interactive Exploration（交互探索）**：从被动阅读升级为主动分析

### 设计参考

- **Perplexity AI**：边搜索边展示结果的渐进式体验
- **Linear**：信息密度高但不压迫的 dashboard 布局
- **Vercel Analytics**：Bento Grid + 清晰的数据层级
- **G2 / Capterra**：竞品对比表的交互模式

---

## 三、改进方案：分阶段详解

---

### Phase 1 重设计：从"死亡等待"到"渐进发现"

#### 3.1 搜索过程中实时预览（Progressive Reveal）

**现状**：用户看到一个竖向时间线，7 个步骤依次点亮，纯被动等待。

**改进**：将页面在搜索阶段就分为**左右两栏**（或上下两区），左侧是紧凑的进度指示器，右侧/下方随着数据到达逐步填充内容。

```
┌──────────────────────────────────────────────────────────────┐
│  ← New search          "AI meeting notes summarizer"         │
├────────────────────┬─────────────────────────────────────────┤
│                    │                                         │
│  ✅ Idea analyzed  │  📋 Your Idea Profile                   │
│     Web app,       │  ┌─────────────────────────────────────┐│
│     productivity   │  │ Type: Web App                       ││
│                    │  │ Category: Productivity / AI         ││
│  🔄 GitHub...      │  │ Keywords: meeting notes, AI,        ││
│     searching      │  │   summarize, transcription          ││
│                    │  │ Target: Teams needing efficient     ││
│  ⏳ Web search     │  │   meeting documentation             ││
│                    │  └─────────────────────────────────────┘│
│  ⏳ Hacker News    │                                         │
│                    │  (this area will fill as data arrives)  │
│  ⏳ Extracting     │                                         │
│  ⏳ Analyzing      │                                         │
│                    │                                         │
└────────────────────┴─────────────────────────────────────────┘
```

**具体行为**：

| SSE Event | 右侧区域变化 |
|-----------|-------------|
| `intent_parsed` | 展示"Idea Profile"卡片 — 应用类型、关键词、目标场景。用户第一时间看到 AI 是如何理解他的想法的 |
| `source_completed` (GitHub) | 出现一个小预览块："Found 23 GitHub repos" + 前 3 个 repo 的名字和星数快速预览 |
| `source_completed` (Tavily) | 追加 Web 搜索预览块，显示发现的前几个产品名 |
| `source_completed` (HN) | 追加 HN 预览块 |
| `extraction_completed` | 预览块更新为："Identified 15 potential competitors"，展示名字列表的快照 |
| `aggregation_completed` | 预览块转变为最终报告的骨架，平滑过渡到完整报告 |

**关键体验提升**：
- 等待变成了"发现"：用户在等待过程中已经开始获取有价值的信息
- 每隔几秒就有新内容出现，保持参与感
- 当最终报告完成时，用户已经对结果有了初步认知，不需要从零开始阅读

#### 3.2 进度指示器精简

**现状**：7 步竖向时间线，占据全屏宽度。

**改进**：改为**水平步骤条**（Horizontal Stepper），固定在页面顶部（sticky），最大程度减少对内容区域的占用。

```
━━━✅━━━━━✅━━━━━🔄━━━━━○━━━━━○━━━━━○━━━━━○━━━
 Parsed   GitHub   Web    HN   Extract  Analyze  Done
                  (23)
```

设计细节：
- 宽度紧凑，一行放下所有步骤
- 完成的步骤显示简要数据（如搜索结果数）
- 当前活跃步骤有**脉冲光晕动画**
- 失败的步骤显示红色 × 但不阻断流程
- 页面滚动时 sticky 在顶部（在 navbar 下方）

#### 3.3 Morphing Transition（形态过渡）

**现状**：进度追踪器消失 → 报告 fade-in，没有视觉连续性。

**改进**：不做硬切换，而是**渐变过渡**：

1. 水平步骤条在最后一步完成时，**向上收缩**并折叠成一个"分析完成"的小徽章（留在页头）
2. 搜索阶段的"Idea Profile"卡片**平滑变形**为报告页的 header 区域
3. 源预览块**展开并重排**为完整的报告 sections
4. 使用 `framer-motion` 的 `layoutId` 实现元素在两个状态间的自动补间动画

效果：用户感受到的是内容"生长"出来了，而不是页面被替换了。

---

### Phase 2 重设计：报告页核心布局

#### 3.4 报告页整体结构 — "叙事仪表盘"

将扁平线性布局重组为**四幕叙事结构**，每幕有明确的视觉分隔和信息目标：

```
┌─────────────────────────────────────────────────────────────────┐
│  NAVBAR:  IdeaGo  ·····  [Share ▾] [Export ▾]  ·  History      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ACT 1: THE VERDICT (一屏看结论)                                 │
│  ┌──────────────────────────────┬──────────────────────────────┐│
│  │                              │                              ││
│  │   🟢 GO                      │   Key Stats                  ││
│  │   "Strong opportunity with   │   ┌────────┬────────┐       ││
│  │    meaningful differentia-   │   │   12   │  68%   │       ││
│  │    tion potential in..."     │   │ Compet- │  Avg   │       ││
│  │                              │   │ itors   │Relevance│      ││
│  │   ┌─ GitHub ✓ 23 (1.2s)     │   ├────────┼────────┤       ││
│  │   ├─ Web    ✓ 15 (2.1s)     │   │  7/10  │  5     │       ││
│  │   └─ HN     ✗ timeout       │   │Competi-│Differe-│       ││
│  │                              │   │ tion   │ntiation│       ││
│  │                              │   │Intensity│Angles ││       ││
│  │                              │   └────────┴────────┘       ││
│  └──────────────────────────────┴──────────────────────────────┘│
│                                                                 │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│                                                                 │
│  ACT 2: THE LANDSCAPE (市场全貌)                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  Market Overview                                            ││
│  │  "The AI meeting notes space is rapidly growing with..."    ││
│  │  ... [Read more]                                            ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │  Competitive Landscape Map (interactive scatter plot)       ││
│  │                                                             ││
│  │    relevance                                                ││
│  │    100% ┤          ● Otter.ai                               ││
│  │         │     ● Fireflies                                   ││
│  │     70% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─              ││
│  │         │  ● Tactiq    ● Fellow                             ││
│  │     40% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─              ││
│  │         │       ● Grain                                     ││
│  │      0% └──────────────────────────────────→                ││
│  │              feature completeness (# features)              ││
│  │                                                             ││
│  │  ● = 1 source   ●● = 2 sources   ●●● = 3 sources          ││
│  │  Click any dot to jump to its competitor card               ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│                                                                 │
│  ACT 3: THE PLAYERS (竞品详情)                                   │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  [Grid ☷] [List ☰] [Compare ⇔]   Filter: [github][web][hn]││
│  │                                    Sort: [Relevance ▾]     ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                             ││
│  │  ┌─ #1 Featured ────────────────────────────────────────┐   ││
│  │  │  ████ Otter.ai                              95% ◐    │  ││
│  │  │  AI-powered meeting transcription & summary           │  ││
│  │  │                                                       │  ││
│  │  │  [Transcription] [AI Summary] [Action Items] [+3]    │  ││
│  │  │                                                       │  ││
│  │  │  ✅ Real-time transcription    ❌ No offline mode     │  ││
│  │  │  ✅ 30+ integrations           ❌ Expensive at scale  │  ││
│  │  │  ✅ Strong mobile app          ❌ English-only        │  ││
│  │  │                                                       │  ││
│  │  │  💰 Freemium, $16.99/mo Pro                           │  ││
│  │  │  github · web · hn     [☐ Compare] [→ Details]        │  ││
│  │  └───────────────────────────────────────────────────────┘  ││
│  │                                                             ││
│  │  ┌─────────────────────┐  ┌─────────────────────┐          ││
│  │  │ #2 Fireflies   88%  │  │ #3 Fellow       72%  │         ││
│  │  │ AI notetaker for... │  │ Meeting producti... │          ││
│  │  │ [tags...] [Compare] │  │ [tags...] [Compare] │         ││
│  │  └─────────────────────┘  └─────────────────────┘          ││
│  │                                                             ││
│  │  ┌─────────────────────┐  ┌─────────────────────┐          ││
│  │  │ #4 Tactiq      58%  │  │ #5 Grain        52%  │         ││
│  │  │ ...                  │  │ ...                  │         ││
│  │  └─────────────────────┘  └─────────────────────┘          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│                                                                 │
│  ACT 4: YOUR EDGE (差异化行动)                                   │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ 💡 Insight 1  │ │ 💡 Insight 2  │ │ 💡 Insight 3  │           │
│  │              │ │              │ │              │            │
│  │ Focus on     │ │ Build native │ │ Offer per-   │            │
│  │ multi-lang   │ │ Slack/Teams  │ │ meeting      │            │
│  │ support      │ │ integration  │ │ pricing      │            │
│  │              │ │              │ │              │            │
│  │ Gap: 10/12   │ │ Gap: 6/12    │ │ Gap: 8/12    │            │
│  │ lack this    │ │ weak here    │ │ don't offer  │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │  📥 Export: [Markdown] [PDF] [PNG Screenshot]               ││
│  │  🔗 Share:  [Copy Link] [Email]                             ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

### 3.5 ACT 1: The Verdict — Hero Summary Panel

#### 设计规格

**布局**：Bento Grid，2 列不等宽。左侧 60%（推荐结论），右侧 40%（关键指标）。

**左列 — Go/No-Go Recommendation**：

```
┌─────────────────────────────────────────┐
│                                         │
│    ◉  ←── 大号圆形指示灯 (48px)         │
│   GO     绿色 #22C55E                   │
│          带径向渐变光晕                   │
│          pulsing glow animation          │
│                                         │
│  "Strong opportunity. The AI meeting    │
│   notes market is growing rapidly but   │
│   lacks multi-language support and      │
│   affordable per-meeting pricing."      │
│                                         │
│  ┌─ Sources ─────────────────────────┐  │
│  │ GitHub ✓ 23  Web ✓ 15  HN ✗      │  │
│  └───────────────────────────────────┘  │
│                                         │
└─────────────────────────────────────────┘
```

- **GO**: 绿色光晕 + `#22C55E` 系
- **CAUTION**: 琥珀色光晕 + `#F59E0B` 系
- **NO-GO**: 红色光晕 + `#EF4444` 系

指示灯使用 CSS radial-gradient + box-shadow 实现光晕，加 `@keyframes pulse` 做呼吸灯效果。

推荐语文字限制 3 行，超出用 line-clamp + "Read more" 展开。

Source Status Bar 集成在推荐卡片底部，改为行内显示（紧凑格式）。

**右列 — Key Stats Grid**：

4 个 Stat Card 组成 2×2 网格：

| Stat Card | 数据 | 说明 |
|-----------|------|------|
| Competitors Found | `12` | report.competitors.length |
| Avg. Relevance | `68%` | 计算平均 relevance_score |
| Competition Intensity | `7/10` | 高相关度竞品占比映射到 1-10 |
| Differentiation Angles | `5` | report.differentiation_angles.length |

每个 Stat Card 设计：
```
┌──────────────────┐
│  12              │  ← 大号数字 (text-3xl font-bold)
│  Competitors     │  ← 小号标签 (text-xs text-text-dim)
│  Found           │
└──────────────────┘
```

背景 `bg-bg-card`，hover 时微微抬起 (translateY -2px + shadow)。

---

### 3.6 ACT 2: The Landscape — 市场概览 + 竞争格局图

#### Market Overview

**现状**：纯文字段落，whitespace-pre-line 直接输出。

**改进**：
- 默认显示前 3 行，带 gradient fade-out 遮罩
- "Read more" 按钮展开全文，使用 `max-height` + `overflow-hidden` + CSS transition
- 为段落添加左侧 2px 彩色竖线装饰（类似 blockquote 但更精致）

#### Competitive Landscape Map（全新组件）

**替代现有的 RelevanceChart**。现有的三条水平进度条信息密度极低，用一个真正的交互式散点图替代。

**设计**：

```
┌─────────────────────────────────────────────────────┐
│  Competitive Landscape                    [?] Help  │
│                                                     │
│  Relevance                                          │
│  100% ┤                                             │
│       │              ◉ Otter.ai                     │
│       │         ◉ Fireflies                         │
│   70% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ HIGH ZONE     │
│       │    ◉ Tactiq                                 │
│       │              ◉ Fellow                       │
│   40% ┤ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─      │
│       │         ◉ Grain                             │
│       │    ◉ MeetNotes                              │
│    0% └──────────────────────────────────────→      │
│        1    2    3    4    5    6    7    8          │
│              Features Count                         │
│                                                     │
│  Bubble size = # of source platforms (1-3)          │
│  Click a bubble to scroll to its competitor card    │
└─────────────────────────────────────────────────────┘
```

**交互规格**：

| 交互 | 行为 |
|------|------|
| Hover 气泡 | 显示 tooltip：竞品名 + 一句话定位 + relevance score |
| Click 气泡 | 平滑滚动到 ACT 3 中对应的 CompetitorCard，并高亮闪烁 |
| Hover 区域线 (70%/40%) | 区域变色提示 High / Medium / Low |

**实现建议**：
- 使用 `recharts` 的 `ScatterChart` 组件（项目已有 React 生态，recharts 轻量）
- 或用纯 SVG 手写（更可控，无额外依赖）
- X 轴：`competitor.features.length`
- Y 轴：`competitor.relevance_score * 100`
- 气泡半径：`competitor.source_platforms.length` 映射到 8px / 12px / 18px

---

### 3.7 ACT 3: The Players — 竞品展示重设计

这是改动最大、价值最高的区域。

#### 3.7.1 视图模式切换

提供三种视图模式，用户通过顶部 toggle 切换：

| 模式 | 图标 | 场景 |
|------|------|------|
| **Grid View** (默认) | ☷ | 快速浏览，视觉丰富 |
| **List View** | ☰ | 信息密集，适合多竞品快速扫描 |
| **Compare View** | ⇔ | 并排对比选中的竞品 |

#### 3.7.2 Grid View 分层设计

**核心改进：Top 竞品和普通竞品使用不同的卡片样式。**

**Featured Card（排名 #1 的竞品）**：
- 全宽单列，高度更大
- 左侧有 4px 宽的 CTA 色竖条
- 默认展开显示所有信息（strengths/weaknesses 全部可见）
- 带有"Top Competitor"徽章

```
┌─ 🏆 Top Competitor ─────────────────────────────────────────┐
│ ████                                                        │
│ ████  Otter.ai                                  95% ◐       │
│       AI-powered meeting transcription & summary             │
│                                                              │
│  [Transcription] [AI Summary] [Action Items] [Search]       │
│  [Speaker ID] [Export]                                       │
│                                                              │
│  💰 Freemium, $16.99/mo Pro, $30/mo Business                │
│                                                              │
│  ┌─ Strengths ─────────────┐  ┌─ Weaknesses ───────────────┐│
│  │ ✅ Real-time transcript  │  │ ❌ No offline mode          ││
│  │ ✅ 30+ integrations      │  │ ❌ Expensive at scale       ││
│  │ ✅ Mobile app             │  │ ❌ English-only ASR         ││
│  │ ✅ Action item extraction │  │ ❌ No self-hosted option    ││
│  └──────────────────────────┘  └────────────────────────────┘│
│                                                              │
│  github · web · hackernews                                   │
│  [otter.ai ↗] [github.com/... ↗]   [☐ Add to Compare]      │
└──────────────────────────────────────────────────────────────┘
```

**Standard Card（#2 及之后）**：
- 两列网格布局（保持现状，但做微调）
- 默认折叠，只显示：名字、一句话定位、relevance 环形图、feature tags（前 3 个）
- 明确的 "Show details" 按钮（不再是整个卡片可点击）

**Relevance Score 环形进度条**（替代纯数字）：

```
    ╭───╮
   │ 95% │   ← 小号环形 (36×36px)
    ╰───╯     绿色 = ≥70%, 琥珀 = ≥40%, 灰色 = <40%
              SVG circle + stroke-dasharray
```

#### 3.7.3 List View（紧凑列表）

适合竞品数量 >10 时快速扫描：

```
┌────┬─────────────┬──────────────────────────┬───────┬──────────┬──────────┐
│ #  │ Name        │ One-liner                │ Score │ Sources  │ Actions  │
├────┼─────────────┼──────────────────────────┼───────┼──────────┼──────────┤
│ 1  │ Otter.ai    │ AI meeting transcript... │ 95%   │ ●●●      │ [⇔] [→] │
│ 2  │ Fireflies   │ AI notetaker for meet... │ 88%   │ ●●       │ [⇔] [→] │
│ 3  │ Fellow      │ Meeting productivity...  │ 72%   │ ●●       │ [⇔] [→] │
│ 4  │ Tactiq      │ Real-time transcript...  │ 58%   │ ●        │ [⇔] [→] │
│ 5  │ Grain       │ Video highlight clip...  │ 52%   │ ●        │ [⇔] [→] │
└────┴─────────────┴──────────────────────────┴───────┴──────────┴──────────┘
```

- 每行 hover 时展开内联预览（features + strengths/weaknesses 的前 2 条）
- `[⇔]` = 添加到对比，`[→]` = 展开详情侧面板

#### 3.7.4 Compare View（对比模式）

**全新功能，竞品分析的核心高价值交互。**

用户在 Grid/List View 中勾选 2-4 个竞品后，切换到 Compare View 或点击底部浮动的 Compare 按钮。

```
┌─────────────────────────────────────────────────────────────────────┐
│  Comparing 3 competitors                            [✕ Clear All]  │
├──────────────┬──────────────┬──────────────┬───────────────────────┤
│              │ Otter.ai     │ Fireflies    │ Fellow               │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Relevance    │ 95%  ●●●●●   │ 88%  ●●●●○   │ 72%  ●●●○○           │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Pricing      │ Free / $17mo │ Free / $10mo │ Free / $6mo           │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Features     │              │              │                       │
│ Transcription│     ✅        │     ✅        │     ❌                │
│ AI Summary   │     ✅        │     ✅        │     ✅                │
│ Action Items │     ✅        │     ❌        │     ✅                │
│ Integrations │     ✅ 30+    │     ✅ 15+    │     ✅ 50+            │
│ Mobile App   │     ✅        │     ✅        │     ❌                │
│ Self-hosted  │     ❌        │     ❌        │     ❌                │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Strengths    │ Real-time,   │ Async-first, │ Deep CRM             │
│              │ Mobile       │ Affordable   │ integration           │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Weaknesses   │ Expensive,   │ No mobile,   │ No transcription,    │
│              │ English-only │ Less accurate│ Complex setup         │
├──────────────┼──────────────┼──────────────┼───────────────────────┤
│ Sources      │ github web hn│ github web   │ web hn               │
└──────────────┴──────────────┴──────────────┴───────────────────────┘
```

**实现要点**：
- Feature 对比行是动态生成的：取所有选中竞品的 features 的并集
- 每个 feature 对应一行，有该 feature 的显示 ✅，没有的显示 ❌
- 表格使用 `sticky` 第一列（attribute 名），水平可滚动（移动端友好）
- 底部浮动按钮在有 ≥2 个竞品被选中时出现：
  ```
  ┌──────────────────────────────────────────┐
  │  ⇔ Compare 3 selected competitors  [Go] │
  └──────────────────────────────────────────┘
  ```

#### 3.7.5 Competitor Card 微交互增强

| 交互 | 现状 | 改进 |
|------|------|------|
| Hover | border-cta/30 + shadow | 加上 subtle translateY(-2px) + 卡片左侧色条从透明变为 relevance 对应色 |
| 展开/折叠 | 整个卡片可点击 | 明确的 "Show details" 文字按钮 + ChevronDown icon |
| Relevance Score | 纯数字 `95%` | 小号环形进度条 (36px) + 数字 |
| 外部链接 | 解析 hostname 后显示 | 加上 favicon（`https://www.google.com/s2/favicons?domain=xxx`）|
| Feature Tags | 全部平铺 | 前 4 个显示，其余收入 "+N more" 弹出层 |

---

### 3.8 ACT 4: Your Edge — 差异化洞察卡片

**现状**：简单的 bullet list，`<ArrowRight>` + 文字。

**改进**：将每个 differentiation angle 做成独立的 **Insight Card**，横向排列或 2-3 列网格。

```
┌──────────────────────────┐
│  💡                       │
│  Multi-language Support   │  ← 标题 (text-sm font-semibold)
│                           │
│  10 out of 12 competitors │  ← 描述 (text-xs text-text-muted)
│  only support English.    │
│  Multi-language ASR       │
│  could be a strong        │
│  differentiator.          │
│                           │
│  Gap Strength: ████░ 4/5  │  ← 可选：如果后端能给出量化数据
└──────────────────────────┘
```

**设计细节**：
- 卡片背景 `bg-cta/5`，border `border-cta/20`
- 顶部有灯泡 icon（保持现有的 Lightbulb）
- 如果后端当前无法提供"Gap Strength"等量化数据，先不加这一行；但预留卡片结构方便未来扩展
- 卡片间距均匀，使用 CSS Grid `auto-fit` 实现自适应列数

---

### 3.9 Header 操作栏重设计

**现状**：Export / Copy Link / Print 三个按钮混在 ReportSummary 组件底部。

**改进**：将操作提升到页面顶部，与标题同行。

```
┌─────────────────────────────────────────────────────────────────┐
│  ← New search                                                   │
│                                                                 │
│  AI meeting notes summarizer                                    │
│  web app · meeting notes, AI, summarize · Feb 22, 2026          │
│                                               ┌─────┐ ┌─────┐  │
│                                               │Share│ │Export│  │
│                                               │  ▾  │ │  ▾  │  │
│                                               └─────┘ └─────┘  │
└─────────────────────────────────────────────────────────────────┘
```

**Share 下拉菜单**：
- Copy Link（带 ✓ 反馈）
- Email（mailto: 链接，subject 预填 report query）

**Export 下拉菜单**：
- Export as Markdown（现有功能）
- Print / Save as PDF（现有 window.print()）
- 未来可扩展：Export as PNG（html2canvas）

使用 Headless UI 的 `Menu` 或 Radix 的 `DropdownMenu` 实现下拉。或者用纯 CSS+state 手写，不引入新依赖。

---

## 四、Section Navigation（可选，P2 优先级）

当竞品数量 >6 且页面较长时，添加一个 **Sticky Section Tab Bar**：

```
┌──────────────────────────────────────────────────────────────────┐
│  [Summary]  [Landscape]  [Competitors (12)]  [Opportunities]    │
└──────────────────────────────────────────────────────────────────┘
```

- 固定在 navbar 下方（当用户开始向下滚动时出现）
- 使用 `IntersectionObserver` 监听各 section 的可见性，自动高亮当前 tab
- 点击 tab 平滑滚动到对应 section
- 移动端：水平可滚动的 tab bar

---

## 五、动效规格

### 5.1 进度阶段动效

| 元素 | 动画 | 规格 |
|------|------|------|
| 活跃步骤 icon | 脉冲光晕 | `@keyframes pulse { 0% { box-shadow: 0 0 0 0 rgba(34,197,94,0.4) } 70% { box-shadow: 0 0 0 10px rgba(34,197,94,0) } }` |
| 步骤完成 | 缩放弹跳 | `scale(0.8) → scale(1.1) → scale(1)`, duration 300ms, ease-out-back |
| 预览块出现 | 从右侧滑入 | `translateX(20px) opacity(0) → translateX(0) opacity(1)`, duration 400ms |

### 5.2 报告展示动效

| 元素 | 动画 | 规格 |
|------|------|------|
| Hero Panel | 从进度区域展开 | `framer-motion layoutId` 或 `max-height` transition, duration 600ms |
| Stat Cards | Stagger fade-in | 4 张卡片间隔 80ms 依次淡入 + 上移 |
| 竞争格局图 | 气泡弹入 | 每个气泡从 scale(0) 弹出，stagger 50ms |
| Competitor Cards | Stagger slide-up | 每张卡片间隔 60ms，从 `translateY(20px) opacity(0)` 到正常位置 |
| Insight Cards | Stagger fade-in | 间隔 100ms |
| 数字计数器 | 数值滚动 | `0 → 12` 在 800ms 内滚动递增，使用 `requestAnimationFrame` |

### 5.3 交互动效

| 交互 | 动画 |
|------|------|
| Card hover | `translateY(-2px)` + `box-shadow` 增强, duration 150ms |
| Card expand | `max-height` 展开, duration 300ms ease-in-out |
| Compare 浮动按钮出现 | 从底部滑入, `translateY(100%) → translateY(0)`, duration 250ms |
| Tab 高亮切换 | 底部指示条 `translateX` 平滑移动, duration 200ms |
| 散点图 tooltip | `opacity(0) → opacity(1)` + `scale(0.95) → scale(1)`, duration 150ms |

---

## 六、响应式适配

### 断点策略

| 断点 | 布局变化 |
|------|---------|
| `≥1024px` (lg) | Hero 双列、Competitors 双列网格、Landscape 图全宽 |
| `768-1023px` (md) | Hero 双列（但 stat cards 2×2 更紧凑）、Competitors 单列 |
| `<768px` (sm) | 全部单列、Hero stats 水平滚动、Landscape 图可横向滑动、Section nav 改为水平滚动 tabs |

### 移动端特殊处理

- **Compare View**：表格改为"滑动卡片"模式（左右滑动切换竞品，属性列表垂直排列）
- **散点图**：改为简化的竖向条形图（在小屏上散点图不好触控）
- **操作栏**：Share/Export 折叠到一个 "..." 菜单中
- **Feature Tags**：默认只显示前 2 个 + "+N"

---

## 七、空状态与边界场景

### 7.1 零竞品（Blue Ocean）

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                    🌊                                            │
│                                                                 │
│           Blue Ocean Detected!                                  │
│                                                                 │
│   We couldn't find direct competitors for your idea.            │
│   This could mean a genuine market gap.                         │
│                                                                 │
│   Suggested next steps:                                         │
│   1. Validate demand with user interviews                       │
│   2. Search for indirect / adjacent competitors                 │
│   3. Consider why no one has built this yet                     │
│                                                                 │
│   [🔄 Try with broader keywords]  [📋 Export this finding]      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.2 全部数据源失败

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│              ⚠️  Couldn't reach data sources                     │
│                                                                 │
│   ✗ GitHub — API rate limit exceeded                            │
│   ✗ Web Search — Network timeout                                │
│   ✗ Hacker News — Service unavailable                           │
│                                                                 │
│   This is usually temporary. Try again in a few minutes.        │
│                                                                 │
│   [🔄 Retry Analysis]                                           │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 7.3 部分降级

当某些数据源失败但有结果时，在 Hero Panel 的 Source Status 行中用 tooltip 显示失败原因，不单独占一个 section。

---

## 八、实施路线图

### Wave 1 — 核心体验升级（建议先做）

| 任务 | 涉及组件 | 预估工作量 | 价值 |
|------|---------|-----------|------|
| Hero Summary Bento Panel | 新组件 `HeroPanel.tsx` | 中 | 最高 |
| Competitor Card 分层（Featured + Standard）| 改造 `CompetitorCard.tsx` | 低-中 | 高 |
| Relevance 环形小图标 | 新组件 `RelevanceRing.tsx` (SVG) | 低 | 中 |
| 操作栏提升到 Header | 改造 `ReportPage.tsx` + `ReportSummary.tsx` | 低 | 中 |
| Insight Cards（替代 bullet list）| 改造 `ReportSummary.tsx` | 低 | 中 |

### Wave 2 — 可视化 + 交互

| 任务 | 涉及组件 | 预估工作量 | 价值 |
|------|---------|-----------|------|
| Competitive Landscape 散点图 | 替换 `RelevanceChart.tsx` | 中 | 高 |
| 进度阶段渐进预览 | 改造 `ProgressTracker.tsx` + `ReportPage.tsx` | 中-高 | 高 |
| 水平步骤条 | 改造 `ProgressTracker.tsx` | 中 | 中 |
| View 模式切换（Grid/List）| 新增 toggle + `CompetitorListRow.tsx` | 中 | 中 |

### Wave 3 — 高级功能

| 任务 | 涉及组件 | 预估工作量 | 价值 |
|------|---------|-----------|------|
| Compare View | 新组件 `ComparePanel.tsx` | 高 | 高 |
| Section Navigation | 新组件 `SectionNav.tsx` | 中 | 中 |
| Morphing Transition（framer-motion）| 改造多个组件 | 高 | 中 |
| 空状态增强 | 改造 `ReportPage.tsx` | 低 | 低 |
| Stagger 入场动画 | 改造各 section | 低 | 低 |

---

## 九、技术依赖评估

| 依赖 | 用途 | 是否必要 | 替代方案 |
|------|------|---------|---------|
| `framer-motion` | layoutId 过渡、stagger 动画 | Wave 1 不需要，Wave 3 需要 | CSS transitions 可以覆盖 Wave 1-2 |
| `recharts` | 散点图 | Wave 2 需要 | 纯 SVG 手写（更轻量但更耗时）|
| `@radix-ui/react-dropdown-menu` | Share/Export 下拉 | 非必要 | 纯 state + CSS 手写 |
| 无新依赖 | Wave 1 全部内容 | - | 纯 Tailwind + CSS |

**建议**：Wave 1 零新依赖，纯 Tailwind CSS 实现。Wave 2 按需引入 `recharts`（~40KB gzip）。Wave 3 按需引入 `framer-motion`（~32KB gzip）。

---

## 十、总结

本方案的核心改变是将报告页从一个**被动阅读的静态文档**转变为一个**主动探索的分析仪表盘**：

1. **等待变发现**：搜索过程中渐进展示预览，消除焦虑
2. **结论先行**：Hero Panel 一屏展示核心判断和关键指标
3. **叙事引导**：四幕结构引导用户从结论到证据到行动
4. **交互深度**：散点图探索 + 多视图切换 + 竞品对比功能
5. **视觉层级**：Featured Card / Standard Card / List Row 的分层设计

每个 Wave 都是独立可交付的，Wave 1 可以在不引入任何新依赖的情况下完成，且已能带来显著的体验提升。
