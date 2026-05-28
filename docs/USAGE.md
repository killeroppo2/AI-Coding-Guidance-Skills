# 使用指南 (Usage Guide)

## 1. 系统概述

AI Coding Guidance Kernel 是一个自我进化的 AI 开发内核，通过有向图工作流来编排编码任务。它能自动选择技能、组装上下文、驱动 AI 执行、反思结果并进化自身的提示词和结构。系统融合了道德经与孙子兵法的哲学思想，指导策略决策——知道何时推进、何时撤退、何时让方案自然涌现。

---

## 2. 安装

### 前置条件

- Python 3.11+
- pip (Python 包管理器)
- Git

### 安装步骤

```bash
# 克隆仓库
git clone <repo-url> && cd AI-Coding-Guidance-Skills

# 安装依赖
pip install pyyaml fastapi uvicorn websockets

# 复制环境配置（可选，用于 Web 仪表盘）
cp .env.example .env

# 验证安装
python runner.py --check
```

---

## 3. 快速开始

三条命令即可上手：

```bash
# 1. 验证图结构（Dry-run，不产生任何副作用）
python runner.py --goal "Build a REST API" --dry-run

# 2. 启动 Web 仪表盘（实时监控）
python -m uvicorn web.app:app --reload

# 3. 真实 AI 执行（需要 AI CLI 工具）
python runner.py --goal "Build a REST API" --ai-command "claude --print"
```

---

## 4. 三种运行模式

### Mode 1: Dry-run（验证图结构）

Dry-run 模式机械地遍历图的每个节点，总是选择第一个可用转换。不调用 AI，不修改工作区文件。用于验证图结构和提示词加载是否正常。

```bash
python runner.py --goal "Build a Todo App" --dry-run
```

**适用场景：**
- 首次使用时验证系统完整性
- 修改 graph.yaml 后验证节点连通性
- CI/CD 中作为冒烟测试

**输出示例：**
```
[DRY-RUN] Node: init -> Transition: goal_loaded -> Next: plan
[DRY-RUN] Node: plan -> Transition: plan_ready -> Next: code
[DRY-RUN] Node: code -> Transition: code_written -> Next: test
...
```

### Mode 2: AI 直接读 BOOT.md（AI 自主运行）

AI 代理直接读取 `kernel/BOOT.md` 作为系统提示词，自主管理状态转换。Runner 不参与。

```bash
# 设定目标
echo "Build a REST API" > memory/current_goal.md

# 让 AI 读取 BOOT.md 并开始工作
# AI 将自行管理 kernel/state.yaml 的读写
```

**适用场景：**
- AI 代理能力足够强，能自主管理状态
- 需要 AI 根据真实判断选择转换路径
- 嵌入在更大的 AI 代理系统中使用

### Mode 3: Runner 调 AI 子进程（自动执行）

Runner 组装完整上下文，通过子进程调用 AI CLI 工具，解析输出中的 `TRANSITION:` 信号来推进状态。

```bash
python runner.py --goal "Build a REST API" --ai-command "claude --print" --verbose
```

**适用场景：**
- 完全自动化执行
- 需要完整的反思和进化循环
- 长时间运行的开发任务

**支持的 AI 命令：**
```bash
--ai-command "claude --print"          # Anthropic Claude CLI
--ai-command "openai chat"             # OpenAI CLI
--ai-command "custom-ai-wrapper"       # 任何返回文本的 CLI 工具
```

---

## 5. Web 仪表盘使用

### 启动方式

```bash
# 默认启动（localhost:8000）
python -m uvicorn web.app:app --reload

# 自定义端口
python -m uvicorn web.app:app --host 0.0.0.0 --port 3000
```

然后访问 `http://localhost:8000` 即可看到仪表盘界面。

### 功能说明

| 功能 | 描述 |
|------|------|
| 状态监控 | 实时显示当前节点、迭代次数、目标、执行状态 |
| 任务管理 | 查看和跟踪任务列表及完成状态 |
| 日志流 | SSE 实时日志推送，无需刷新页面 |
| 进化历史 | 查看所有进化变更的时间线 |
| 指标图表 | Chart.js 可视化成功率、迭代分布、进化速度 |
| 技能列表 | 查看已加载的技能清单 |
| 目标设定 | 通过 Web 界面设定新的开发目标 |
| 执行控制 | 启动/停止内核执行 |

### API 端点列表

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/` | HTML 仪表盘页面 |
| GET | `/api/state` | 当前内核状态 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/history` | 进化历史 |
| GET | `/api/reflections` | 最近 20 条反思记录 |
| GET | `/api/skills` | 技能清单 |
| GET | `/api/metrics` | 系统指标 |
| GET | `/api/metrics/history` | 指标时序数据 |
| GET | `/api/logs` | SSE 实时日志流 |
| POST | `/api/goal` | 设定开发目标 |
| POST | `/api/start` | 启动执行 |
| POST | `/api/stop` | 停止执行 |
| WS | `/ws` | WebSocket 双向实时通信 |

详细 API 文档请参阅 [api-reference.md](./api-reference.md)。

---

## 6. CLI 完整参数说明

| 参数 | 类型 | 默认值 | 描述 |
|------|------|--------|------|
| `--goal` | string | - | 开发目标，内核将围绕此目标工作 |
| `--dry-run` | flag | false | 仅遍历图结构，不调用 AI |
| `--ai-command` | string | - | AI CLI 命令（如 `"claude --print"`） |
| `--check` | flag | false | 运行环境检查后退出 |
| `--status` | flag | false | 打印当前状态后退出 |
| `--resume` | flag | false | 从保存的状态恢复，而非重新开始 |
| `--max-iterations` | int | 30 | 最大迭代次数 |
| `--skills` | string | - | 逗号分隔的技能名，覆盖自动选择 |
| `--execution-mode` | string | kernel | `kernel`（默认）或 `ralph`（规划后导出 prd.json） |
| `--retry-strategy` | string | continue | 失败策略：`continue`/`skip`/`backoff` |
| `--timeout` | int | 300 | 每次迭代超时秒数 |
| `--verbose` | flag | false | 显示逐次迭代的详细进度 |
| `--generate-prompt` | flag | false | 输出组装后的提示词到 stdout |
| `--workspace` | string | - | 手动指定工作区项目名 |

**使用示例：**

```bash
# 指定技能，跳过自动选择
python runner.py --goal "Design a landing page" --skills "ui-ux-pro-max,design-system"

# 从中断处恢复执行
python runner.py --resume --ai-command "claude --print"

# 限制迭代次数，使用退避策略
python runner.py --goal "Fix login bug" --max-iterations 10 --retry-strategy backoff

# Ralph 模式：规划后导出 PRD
python runner.py --goal "Build user auth" --execution-mode ralph

# 只生成提示词，不执行
python runner.py --goal "Build a CLI tool" --generate-prompt > prompt.txt
```

---

## 7. 技能系统

### 技能列表（按工作流阶段分组）

#### 创意阶段 (Idea Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `grill-me` | 通过严格质问来挑战和厘清想法 | grill-with-docs, to-prd |
| `grill-with-docs` | 用文档和 ADR 格式来挑战想法 | grill-me, to-prd |

#### 需求阶段 (Requirements Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `prd` | 生成产品需求文档（含澄清问题和结构化输出） | ralph, to-issues, grill-me |
| `to-prd` | 将想法转换为产品需求文档 | prd, grill-me, to-issues |
| `to-issues` | 将 PRD/计划转换为可执行的 Issue | prd, to-prd, ralph |

#### 执行阶段 (Execution Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `ralph` | 自主编码代理，逐个实现用户故事 | prd, tdd, diagnose |
| `tdd` | 测试驱动开发，深度模块和接口设计 | ralph, diagnose, prototype |
| `prototype` | 快速原型开发，含逻辑和 UI 模板 | tdd, ui-ux-pro-max |

#### 质量阶段 (Quality Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `diagnose` | 调试和诊断问题（含 HITL 循环） | ralph, tdd |
| `improve-codebase-architecture` | 重构和架构改进 | diagnose, zoom-out |
| `relentless-iteration` | 持续挑刺修复，直到产品级质量 | tdd, diagnose, improve-codebase-architecture |

#### 设计阶段 (Design Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `ui-ux-pro-max` | UI/UX 设计：50+ 风格、161 色板、57 字体组合 | ui-styling, design-system, brand |
| `ui-styling` | Tailwind CSS + shadcn/ui 组件样式 | ui-ux-pro-max, design-system |
| `design-system` | 设计令牌、组件规格、幻灯片生成 | ui-ux-pro-max, ui-styling, brand |
| `design` | 综合设计：Logo、CIP、图标、幻灯片 | brand, ui-ux-pro-max, banner-design |
| `brand` | 品牌识别管理：指南、语气、视觉 | design, design-system, ui-ux-pro-max |
| `banner-design` | Banner 创作（含尺寸和风格参考） | brand, design |
| `slides` | HTML 演示文稿创建（含布局模式） | design-system, brand |

#### 生命周期阶段 (Lifecycle Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `handoff` | 会话结束交接文档 | zoom-out |
| `triage` | 问题分类和优先级排序 | to-issues, diagnose |
| `zoom-out` | 项目状态全局视图 | improve-codebase-architecture, handoff |

#### 数据阶段 (Data Phase)

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `web-scraper` | 网页抓取（含提取模式和数据转换） | xhs_collector |
| `xhs_collector` | 小红书内容采集（含调度） | web-scraper |

#### 其他

| 技能 | 描述 | 可组合 |
|------|------|--------|
| `write-a-skill` | 元技能：用于创建新技能 | - |
| `caveman` | 简化沟通风格 | - |
| `ai-product` | AI 产品开发指导 | prd, prototype |
| `ai-code-guidance` | AI 编码指导和最佳实践 | tdd, ralph |

### 如何使用技能

**自动选择（推荐）：**

内核根据目标文本中的关键词自动匹配最相关的技能：

```bash
# 内核会自动选择 ralph, tdd 等执行阶段技能
python runner.py --goal "Build a REST API with tests"
```

**手动指定：**

```bash
# 强制使用特定技能组合
python runner.py --goal "Design a dashboard" --skills "ui-ux-pro-max,design-system,brand"
```

### 如何创建新技能

使用 `write-a-skill` 元技能来脚手架新技能：

```bash
python runner.py --goal "Create a new skill for database migration" --skills "write-a-skill"
```

或者手动创建：

1. 在 `skills/` 下创建目录，包含 `SKILL.md` 文件
2. 在 `skills/_index.yaml` 中注册：

```yaml
- name: my-new-skill
  path: my-new-skill
  description: "描述这个技能做什么"
  tags: [relevant, tags, here]
  composable_with: [other-skill-1, other-skill-2]
```

3. `SKILL.md` 中编写技能的行为和提示词

### 技能组合

技能可以组合使用以获得更强的效果：

```bash
# 从创意到执行的完整流程
python runner.py --goal "Build a SaaS app" --skills "grill-me,prd,to-issues,ralph"

# 设计驱动开发
python runner.py --goal "Redesign checkout flow" --skills "ui-ux-pro-max,ui-styling,design-system"

# 质量强化
python runner.py --goal "Fix production bugs" --skills "diagnose,tdd,relentless-iteration"
```

---

## 8. 工作流说明

### 完整工作流（技能层面）

典型的端到端开发流程：

```
grill -> prd -> to-issues -> ralph -> diagnose -> improve -> handoff
```

| 步骤 | 技能 | 产出 |
|------|------|------|
| 1. 质问 | grill-me | 经过验证的想法 |
| 2. 需求 | prd | 产品需求文档 |
| 3. 拆分 | to-issues | 可执行的 Issue 列表 |
| 4. 实现 | ralph | 可运行的代码 |
| 5. 诊断 | diagnose | Bug 修复报告 |
| 6. 改进 | improve-codebase-architecture | 重构后的代码 |
| 7. 交接 | handoff | 交接文档 |

### 图节点说明（内核层面）

```
init -> plan -> code -> test -> review -> reflect -> evolve
                 ^                 |         |         |
                 |                 |         |         |
                 +-- tests fail ---+         |         |
                 |                           |         |
                 +-- needs changes ----------+         |
                 |                                     |
                 +---- evolution applied -------------+
```

| 节点 | 提示词文件 | 描述 | 转换条件 |
|------|-----------|------|----------|
| `init` | orchestrator.md | 初始化上下文，加载目标 | goal_loaded -> plan |
| `plan` | planner.md | 拆解目标为任务，创建执行计划 | plan_ready -> code |
| `code` | coder.md | 实现计划中的下一个任务 | code_written -> test |
| `test` | tester.md | 运行测试，验证覆盖率 | tests_pass -> review |
| `review` | reviewer.md | 代码审查：质量和模式 | review_pass -> reflect |
| `reflect` | reflector.md | 分析迭代，提取经验，提议进化 | evolution_proposed -> evolve |
| `evolve` | reflector.md | 应用已批准的进化变更 | evolution_applied -> plan |

**卡住处理 (stuck_handler)：** `code` 和 `test` 节点如果重试超限，会转入 `reflect` 节点进行分析。

---

## 9. 自我进化机制

### 什么可以被修改

- `kernel/prompts/` 下的提示词文件
- `kernel/graph.yaml` 中的节点结构和转换
- `skills/_index.yaml` 中的技能配置
- `knowledge/rules.yaml` 中的规则

### 什么不可以被修改（宪法保护）

- `kernel/constitution.md` - 安全约束
- `kernel/BOOT.md` - 引导序列
- `runner.py` - 核心执行逻辑

这三个文件构成系统的不可变核心。任何试图修改它们的进化提案都会被自动拒绝。

### 进化如何触发

1. 每次迭代后 `FeedbackLoop` 收集执行数据
2. `Reflector` 分析最近 10 次反思，检测模式
3. 如果同一节点连续失败 3+ 次，生成进化提案
4. 提案计算置信度分数（数据因子 x 一致性因子）
5. 置信度 > 0.7 的提案自动应用
6. 每个反馈周期最多应用 1 个提案

### 回滚机制

- 应用变更前快照当前指标
- 变更生效数次迭代后比较新旧指标
- 如果成功率下降超过 10%，自动回滚
- 所有变更（应用/拒绝/回滚）记录在 `kernel/evolution/history.jsonl`

详细进化机制请参阅 [evolution-guide.md](./evolution-guide.md)。

---

## 10. 配置说明

### kernel/graph.yaml 结构

```yaml
version: "1.0"
description: "工作流描述"

nodes:
  - id: node_name           # 节点唯一标识
    prompt_file: prompts/x.md  # 对应的提示词文件
    description: "节点描述"
    transitions:
      - to: next_node       # 目标节点
        condition: "signal" # 转换条件（从 AI 输出中匹配）
    max_retries: 5          # 最大重试次数
    stuck_handler: reflect  # 卡住时转入的节点（可选）

default_start: init         # 起始节点
max_iterations: 30          # 全局最大迭代
```

### kernel/state.yaml 字段

```yaml
current_node: init          # 当前执行节点
iteration_count: 0          # 已执行迭代数
max_iterations: 30          # 最大迭代数
goal: ""                    # 当前开发目标
status: idle                # 状态：idle/running/completed/error
last_updated: ""            # 最后更新时间
errors: []                  # 最近错误列表（最多 10 条）
context:
  skills_loaded: []         # 已加载技能列表
  current_task: ""          # 当前执行的任务
  phase: "startup"          # 当前阶段
```

### memory/progress.yaml 格式

```yaml
iteration: 5                # 当前迭代数
tasks_total: 8              # 总任务数
tasks_done: 3               # 已完成任务数
status: in_progress         # pending/in_progress/completed
```

### 环境变量 (.env)

```bash
HOST=0.0.0.0                # Web 服务监听地址
PORT=8000                   # Web 服务端口
CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000  # 允许的跨域来源
RATE_LIMIT_PER_MINUTE=60    # 每 IP 每分钟请求限制
KERNEL_ROOT=.               # 内核根目录
```

---

## 11. 常见问题 (FAQ)

**Q: 运行 `--dry-run` 报错找不到 graph.yaml？**

A: 确保从项目根目录运行命令，且 `kernel/graph.yaml` 文件存在。

**Q: Web 仪表盘无法访问？**

A: 检查端口是否被占用 (`lsof -i :8000`)，确认 fastapi 和 uvicorn 已安装。

**Q: AI 命令执行没有输出？**

A: 确保 `--ai-command` 指定的命令能在终端独立运行。AI 输出必须包含 `TRANSITION: <condition>` 行。

**Q: 进化没有触发？**

A: 进化需要足够的数据积累。同一节点至少失败 3 次才会生成提案，且置信度需超过 0.7。

**Q: 如何重置状态从头开始？**

A: 直接编辑 `kernel/state.yaml`，将 `current_node` 设为 `init`，`iteration_count` 设为 0。或者不使用 `--resume` 参数即可重新开始。

**Q: 如何查看执行历史？**

A: 查看以下文件：
- `memory/decisions.jsonl` - 决策日志
- `memory/reflections.jsonl` - 反思记录
- `kernel/evolution/history.jsonl` - 进化历史

**Q: 测试覆盖率不够怎么办？**

A: 宪法要求维持 90%+ 覆盖率。运行 `python -m pytest tests/ --cov --cov-fail-under=90` 查看不足的地方。

**Q: 技能自动选择不准确？**

A: 使用 `--skills` 参数手动指定技能组合。自动选择基于目标文本的关键词匹配。

**Q: 如何在团队中共享进化结果？**

A: 提交 `kernel/evolution/history.jsonl` 和修改后的提示词文件到 Git。其他人拉取后即可获得进化成果。

---

## 12. 示例场景

### 场景 1: 用它开发一个 Todo App

```bash
# 第一步：质问想法，确保方向正确
python runner.py --goal "Build a full-stack Todo app with React and FastAPI" \
  --skills "grill-me" --max-iterations 3

# 第二步：生成需求文档
python runner.py --goal "Build a full-stack Todo app with React and FastAPI" \
  --skills "prd" --max-iterations 5

# 第三步：自主编码实现
python runner.py --goal "Build a full-stack Todo app with React and FastAPI" \
  --ai-command "claude --print" --verbose

# 或者一步到位，让内核自动走完整流程
python runner.py --goal "Build a full-stack Todo app with React and FastAPI" \
  --ai-command "claude --print" --max-iterations 30 --verbose
```

**期望产出：**
- `workspace/build-a-full-stack-todo-app/` 目录下的完整代码
- React 前端 + FastAPI 后端
- 测试文件和文档

### 场景 2: 用它开发一个 CLI 工具

```bash
# 使用 TDD 驱动开发一个 CLI 工具
python runner.py \
  --goal "Build a CLI tool that converts CSV to JSON with filtering and sorting" \
  --skills "tdd,ralph" \
  --ai-command "claude --print" \
  --max-iterations 20 \
  --verbose

# 开发完成后进行质量检查
python runner.py \
  --goal "Review and improve the CSV-to-JSON CLI tool" \
  --skills "diagnose,improve-codebase-architecture" \
  --ai-command "claude --print" \
  --max-iterations 10
```

**期望产出：**
- 完整的 CLI 工具，支持参数解析
- 单元测试和集成测试
- 使用文档

### 场景 3: 用它做 UI 设计

```bash
# 设计一个 SaaS 产品的着陆页
python runner.py \
  --goal "Design a modern SaaS landing page with dark mode, gradient accents, and responsive layout" \
  --skills "ui-ux-pro-max,design-system,brand" \
  --ai-command "claude --print" \
  --max-iterations 15

# 然后用 Tailwind 实现样式
python runner.py \
  --goal "Implement the landing page design using Tailwind CSS and shadcn/ui" \
  --skills "ui-styling,prototype" \
  --ai-command "claude --print" \
  --max-iterations 15
```

**期望产出：**
- 设计令牌和色板定义
- 组件规格文档
- Tailwind CSS 实现的响应式页面
- 暗色/亮色模式支持

---

## 附录：项目目录结构

```
AI-Coding-Guidance-Skills/
├── runner.py              # 入口点（不可修改）
├── kernel/
│   ├── BOOT.md            # AI 代理引导文件（不可修改）
│   ├── constitution.md    # 宪法安全规则（不可修改）
│   ├── graph.yaml         # 工作流图定义
│   ├── state.yaml         # 当前执行状态
│   ├── prompts/           # 各节点提示词
│   ├── philosophy/        # 哲学指导（道德经、兵法）
│   ├── contracts/         # 输出格式和协议约定
│   ├── evolution/         # 进化历史和归档
│   └── skill_selector.py  # 技能自动选择器
├── skills/                # 技能库
│   ├── _index.yaml        # 技能索引
│   └── <skill-name>/      # 各技能目录
├── memory/                # 状态和日志
│   ├── state_manager.py   # 状态管理器
│   ├── decisions.jsonl    # 决策日志
│   ├── reflections.jsonl  # 反思记录
│   └── progress.yaml      # 进度追踪
├── knowledge/             # 知识库
│   └── store.py           # 规则和模式存储
├── web/                   # Web 仪表盘
│   └── app.py             # FastAPI 应用
├── workspace/             # AI 生成的代码（隔离区）
├── tests/                 # 测试套件
├── docs/                  # 文档
│   ├── USAGE.md           # 本文档
│   ├── api-reference.md   # API 参考
│   ├── architecture.md    # 架构说明
│   └── evolution-guide.md # 进化指南
└── examples/              # 使用示例
    ├── todo_app/
    ├── cli_tool/
    └── api_service/
```
