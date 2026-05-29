[English](README.md) | [中文](README_CN.md)

# AI-Coding-Guidance-Skills

> 一个自我进化的 AI 开发内核，编排编码工作流、从经验中学习，并自适应调整自身行为。

![Tests](https://img.shields.io/badge/tests-passing-green)
![Coverage](https://img.shields.io/badge/coverage-98%25-brightgreen)

## 最新动态

- **核心/社区技能分离** - 12 个核心技能用于聚焦工作流，17 个社区技能用于专业领域
- **PyPI 发布就绪** - 通过 `pip install ai-coding-guidance-skills` 安装
- **演示展示** - `examples/` 目录中提供了示例场景，方便学习内核

## 这是什么？

这是一个通过有向图节点驱动 AI 开发工作流的内核。它从可扩展的技能库中选择技能，为每个阶段组装丰富的上下文，通过 AI 命令执行，反思结果，并随时间演进自身的提示词和结构。内核将东方哲学（道德经、孙子兵法）与软件工程相结合，指导战略决策——知道何时推进、何时撤退、何时顺其自然。

## 架构

内核作为状态机遍历以下有向图：

```
[init] --> [plan] --> [code] --> [test] --> [review] --> [reflect] --> [evolve]
   ^                    ^                      |             |            |
   |                    |                      |             |            |
   |                    +---- (tests fail) ----+             |            |
   |                    |                                    |            |
   |                    +---- (needs changes) ---------------+            |
   |                                                                     |
   +--- (no evolution needed) --- [reflect]                              |
   |                                                                     |
   +----------------------- (evolution applied) -------------------------+
```

每个节点加载专用提示词，从技能和记忆中组装上下文，调用 AI，并根据输出信号进行状态转换。

## 快速开始

```bash
# 方式 A：从 PyPI 安装
pip install ai-coding-guidance-skills
ai-kernel --goal "Build a REST API" --dry-run

# 方式 B：克隆进行开发
# 1. 克隆并进入目录
git clone <repo-url> && cd AI-Coding-Guidance-Skills

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 初始化运行时文件
python runner.py --init

# 4. 干运行以验证图结构
python runner.py --goal "Build a REST API" --dry-run

# 5. 使用 AI 进行真实执行
python runner.py --goal "Build a REST API" --ai-command "claude --print"
```

## 三种执行模式

| 模式 | 命令 | 使用场景 |
|------|------|----------|
| 干运行 | `runner.py --goal "..." --dry-run` | 验证图结构，不修改状态 |
| BOOT.md | AI 直接读取 `BOOT.md` | Agent 自行管理状态转换 |
| 自主模式 | `runner.py --goal "..." --ai-command "claude --print"` | 使用 AI 子进程的完全自主循环 |

## 功能特性

- 通过反思和进化节点实现提示词与图结构的自我演进
- 基于目标分析和阶段匹配的技能自动选择
- 哲学指导决策（战略撤退、地形感知、自然流动）
- 可组合的技能系统，共 29 个技能（12 个核心 + 17 个社区）
- Token 预算感知的上下文组装，包含工作区和决策历史
- 带咨询锁的并发安全文件操作
- 仅追加的 JSONL 进化历史，支持自动修剪
- 可配置的重试策略（继续、跳过、退避）
- 支持从保存状态恢复中断的会话
- Ralph 模式用于自主编码并导出 PRD

## 技能清单

### 核心技能（12 个）

| 技能 | 阶段 | 描述 |
|------|------|------|
| grill-me | idea | 通过严格提问来挑战和澄清想法 |
| grill-with-docs | idea | 使用文档和 ADR 格式挑战想法 |
| prd | requirements | 生成具有结构化输出的产品需求文档 |
| to-issues | requirements | 将 PRD/计划转换为可执行的 Issue |
| ralph | execution | 自主编码代理，实现用户故事 |
| tdd | execution | 测试驱动开发，深度模块与接口设计 |
| prototype | execution | 使用逻辑和 UI 模板的快速原型开发 |
| diagnose | quality | 带 HITL 循环的调试和诊断 |
| relentless-iteration | quality | 多轮批判性迭代，打造生产级输出 |
| handoff | lifecycle | 会话结束的交接文档 |
| zoom-out | lifecycle | 项目状态的高层视角审视 |
| write-a-skill | meta | 用于创建新技能的元技能 |

### 社区技能（17 个）

| 技能 | 阶段 | 描述 |
|------|------|------|
| to-prd | requirements | 将想法转换为产品需求文档 |
| improve-codebase-architecture | quality | 重构和架构改进 |
| ux-audit | quality | 从真实用户视角进行 UX 审计 |
| ui-ux-pro-max | design | UI/UX 设计，50+ 风格、161 调色板、57 字体配对 |
| ui-styling | design | Tailwind CSS 和 shadcn/ui 组件样式 |
| design-system | design | 设计令牌、组件规范和幻灯片生成 |
| design | design | 综合设计 - 标志、CIP、图标、幻灯片 |
| brand | design | 品牌识别管理 - 指南、声音、视觉识别 |
| banner-design | design | 带尺寸和风格参考的横幅创建 |
| slides | design | 带布局模式的 HTML 演示文稿创建 |
| triage | lifecycle | 分流和优先排序 Issue 与任务 |
| web-scraper | data | 带提取模式和转换的网页抓取 |
| xhs_collector | data | 小红书内容采集，支持定时调度 |
| caveman | style | 简化沟通风格 |
| ai-product | strategy | AI 产品开发指导 |
| ai-code-guidance | guidance | AI 编码指导和最佳实践 |
| setup-matt-pocock-skills | setup | 设置 Matt Pocock 的技能配置 |

## 工作原理

1. **目标设定** - 通过 `--goal` 提供开发目标。内核初始化上下文并加载相关状态。
2. **技能自动选择** - 技能选择器分析目标，与技能标签匹配，为当前阶段加载最佳技能。
3. **图遍历** - 执行器从 `init` 开始，依次经过 `plan`、`code`、`test`、`review`、`reflect`，可选地进入 `evolve`，根据 AI 输出的转换条件进行状态流转。
4. **上下文组装** - 每个节点组装提示词，结合节点模板、选定技能内容、记忆状态、进度历史和工作区上下文，控制在 Token 预算内。
5. **AI 执行** - 组装好的提示词被传送给 AI 命令（模式 3）或呈现供手动执行（模式 2）。解析输出中的转换信号。
6. **反思与进化** - 反思器分析迭代结果，提取经验教训，提出结构性改进。进化引擎将批准的变更应用到提示词、图结构或技能配置中。

## 哲学理念

内核汲取两大哲学传统来指导其行为：

- **道德经** - 大道至简。知止不殆。让解决方案自然涌现，而非强行推动。「道生一，一生二，二生三，三生万物」——内核避免过度工程化，尊重开发的自然节奏。「知足不辱，知止不殆，可以长久。」
- **孙子兵法** - 陷入困境时战略撤退（stuck_handler 节点）。地形感知（上下文组装映射当前态势）。通过进化实现适应性。「兵无常势，水无常形，能因敌变化而取胜者，谓之神。」内核将每次迭代视为一场战役，而非一次战斗。

## CLI 参考

| 参数 | 描述 |
|------|------|
| `--goal` | 要达成的开发目标 |
| `--init` | 初始化运行时文件并退出 |
| `--dry-run` | 打印将要执行的操作，不修改状态 |
| `--ai-command` | 用于自主执行的 AI CLI 命令（如 `"claude --print"`） |
| `--provider` | AI 提供商：`cli`（默认）、`openai` 或 `anthropic` |
| `--model` | openai/anthropic 提供商的模型名称（如 `gpt-4o`、`claude-sonnet-4-20250514`） |
| `--check` | 运行设置检查并退出 |
| `--status` | 打印当前状态并退出 |
| `--resume` | 从保存状态继续，而非重新开始 |
| `--max-iterations` | 最大迭代次数（默认：30） |
| `--skills` | 逗号分隔的技能名称，用于加载（覆盖自动选择） |
| `--execution-mode` | `kernel`（默认）或 `ralph`（规划后导出 prd.json） |
| `--complexity` | 任务复杂度：`auto`（默认）、`low`、`medium` 或 `high` |
| `--retry-strategy` | 失败时的策略：`continue`、`skip` 或 `backoff` |
| `--timeout` | 每次迭代的超时时间，单位秒（默认：300） |
| `--verbose` | 显示逐次迭代的进度 |
| `--generate-prompt` | 输出组装好的提示词到标准输出并退出 |
| `--workspace` | 手动覆盖工作区项目名称 |
| `--migrate` | 运行待处理的数据迁移并退出 |

## 贡献指南

### 添加新技能

1. 在 `skills/` 下创建目录，包含描述技能行为和提示词的 `SKILL.md` 文件。
2. 在 `skills/_index.yaml` 中注册，填写 name、path、description、tags 和 composable_with 字段。
3. 使用 `write-a-skill` 元技能搭建结构：运行时使用 `--skills write-a-skill`。

### 运行测试

```bash
pip install -e ".[dev]"
python -m pytest tests/ --cov --cov-fail-under=90 -q
```

## 许可证

本项目基于 Apache License 2.0 许可 - 详见 [LICENSE](LICENSE) 文件。
