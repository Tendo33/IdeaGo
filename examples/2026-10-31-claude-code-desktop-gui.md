# 给 Claude Code 做一个桌面 GUI

> 2026-10-31 · desktop · 让不习惯终端的开发者用图形界面驱动 Claude Code 会话

## 1. 结论：NO-GO（通用桌面 GUI）

官方已在 2026-04 推出重做的 Claude Code 桌面版，覆盖多会话侧栏、diff、终端、预览和插件，且随 Pro 订阅免费提供 [1][2]；开源侧还有 opcode（22k★）、CloudCLI（14k★）等成熟方案 [5][6]。再做一个“通用 GUI”基本没有切入空间。若仍想做，只剩下官方不覆盖的窄缝：例如跨 Claude Code / Codex 的统一工作台，或面向 JetBrains 等非 VS Code 生态的深度集成（后者也已有 7k★ 项目）[7]。

**Why now：** 时机不利——官方产品刚完成重做并持续迭代，窗口正在关闭而不是打开。

**机会分：** 0.36 — 痛点 0.5 · 缺口 0.2 · 付费 0.3 · 新鲜度 0.9 · 竞争 0.9

## 2. 痛点信号

| 主题 | 强度 | 频率 | 证据 |
|---|---|---|---|
| 官方桌面版在 Windows 上卡顿、黑屏、无法启动 | 高 | 中 | [8] [9] |
| 官方桌面版选项过多、界面拥挤 | 中 | 低 | [4] |
| 从 Cursor 转来的用户觉得 CLI 门槛高 | 中 | 中 | [10] |

痛点集中在官方产品的稳定性与易用性，属于官方会修的问题，而非结构性空白。

## 3. 付费信号

- **托管运行环境** — CloudCLI Cloud 从 €7/月起，卖的是“机器关了也能跑 + 团队共享”，AI 订阅仍需自备。[6]
- 官方 GUI 包含在 Claude 订阅里，第三方 Nimbalyst 对个人免费 [3]：通用 GUI 本身几乎没有定价空间。

迁移：有作者在比较后偏好 Codex 桌面版 [4]，说明用户会在官方产品之间切换，而不是转向第三方 GUI。

## 4. 空白机会

### 多 agent 统一工作台
- **缺口：** 官方桌面版只服务自家 agent；同时用 Claude Code 与 Codex 的人要开两个 app。
- **面向：** 同时订阅多家 agent 的重度开发者 / 小团队
- **切入：** 共享会话历史与 diff 审阅，跨 agent 并行任务看板
- **证据：** [6] [11]（已有 CloudCLI、Kanna 往这个方向走，空间有限）

**差异化角度：**
- 官方版 Windows 稳定性差 [8][9]
- 官方版 Chat / Cowork / Code 三套设置分散 [4]
- CloudCLI 是 AGPL，对想闭源集成的团队不友好 [6]

## 5. 竞品

### 直接竞品
| 产品 | 做什么 | 价格 | 热度 | 优势 | 劣势 |
|---|---|---|---|---|---|
| [Claude Code Desktop](https://claude.com/blog/claude-code-desktop-redesign) | 官方桌面版，多会话 + diff + 终端 + 预览 | 含在 Pro $20/月起 | 官方 | 原生集成、插件对齐 CLI | Windows 问题、界面拥挤 |
| [opcode](https://github.com/winfunc/opcode) | Claude Code 桌面 GUI | 开源 | 22k★ | 社区大 | 最近更新 2026-09 |
| [CloudCLI](https://github.com/siteboon/claudecodeui) | Web/移动端 UI，支持多 agent | 开源 + Cloud €7/月 | 14k★ | 远程、移动、多 agent | AGPL |
| [jetbrains-cc-gui](https://github.com/zhukunpenglinyutong/jetbrains-cc-gui) | JetBrains 内的 Claude Code GUI | 开源 | 7.3k★ | 填补 JetBrains 生态 | 单一 IDE |
| [Nimbalyst](https://nimbalyst.com/claude-code-desktop-app/) | 开源桌面工作区 | 个人免费 | — | 跨平台 | — |

### 相邻
Codex 桌面版 [4]、Cursor。

赛道拥挤，主流做法是“包一层会话管理 + diff + 终端”，同质化严重。

## 6. 证据

1. [Redesigned Claude Code Desktop app](https://claude.com/blog/claude-code-desktop-redesign) — 官方博客, 2026-04 — "built to help you run more Claude Code tasks at once"
2. [Anthropic Rebuilds Claude Code Desktop App](https://www.macrumors.com/2026/04/15/anthropic-rebuilds-claude-code-desktop-app/) — HN, 2026-04-15
3. [Claude Code pricing](https://www.lowcode.agency/blog/claude-code-pricing) — web, 2026-09
4. [Codex vs. Claude Code Desktop Apps](https://catalins.tech/codex-vs-claude-code-desktop-apps/) — HN, 2026-06 — "Claude Code overwhelms you with options"
5. [winfunc/opcode](https://github.com/winfunc/opcode) — GitHub, 22k★
6. [siteboon/claudecodeui](https://github.com/siteboon/claudecodeui) — GitHub, 14k★ — "Starts at €7/month"
7. [jetbrains-cc-gui](https://github.com/zhukunpenglinyutong/jetbrains-cc-gui) — GitHub, 7.3k★
8. [anthropics/claude-code#21764](https://github.com/anthropics/claude-code/issues/21764) — "This is frustrating for customers who rely on Claude Code"
9. [anthropics/claude-code#42045](https://github.com/anthropics/claude-code/issues/42045) — 流式输出时桌面卡顿
10. [I Used Claude Code for 30 Days](https://alekdobrohotov.substack.com/p/i-used-claude-code-for-30-days-7) — "felt like a step backward" coming from Cursor
11. [Show HN: Kanna](https://github.com/jakemor/kanna) — HN, 2026-03 — Claude Code + Codex Web UI

## 7. 置信度：69/100

- 来源：3/4 可用（Reddit 无法获取：site 过滤未生效）
- 竞品与官方动态证据充分、且新鲜
- 付费信号薄弱，只有 CloudCLI 一个定价点
- 痛点证据多来自 GitHub issue，缺少真实用户讨论（Reddit 缺失）
