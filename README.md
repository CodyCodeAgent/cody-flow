# CodyFlow

AI 工作流编排框架 —— 让 AI 编程 Agent 按照你设计的流程自动完成复杂任务。

## 背景与动机

在使用 AI 编程 Agent（如 Cody、Claude Code）的日常开发中，我们发现一个普遍的问题：

> 让 AI 写完代码后，你让它自检，它能检查出问题。改完后再检查，还是能发现问题。
> 你不得不手动重复"写 → 检查 → 修 → 再检查"这个循环。

这个过程是机械的、可自动化的。CodyFlow 就是要把这种**人工驱动的 AI 交互模式**，变成**可配置、可自动执行的工作流**。

## 这是什么

CodyFlow 是一个**节点式工作流编排框架**：

- 你可以配置**节点**（讨论、学习、写代码、反思、判断……）
- 节点之间用**连线**串联，形成一个流程图
- 每个节点由底层的 AI Agent（Cody SDK / Claude Code SDK）驱动执行
- 流程自动运转：写代码 → 反思 → 判断 → 需要修改则回到写代码 → 直到通过

你只需要**设计流程 + 发起任务**，CodyFlow 会自动驱动 AI 按流程完成工作。

## 核心概念

### Node（节点）

每个节点代表一个 AI 执行的步骤。系统内置 6 种节点类型：

| 节点类型 | 用途 | 默认行为 |
|---------|------|---------|
| **discuss** | 讨论需求 | 与用户多轮对话，分析需求，产出讨论结论 |
| **learn** | 学习项目 | AI 自主浏览项目代码，整理技术栈和架构知识 |
| **code** | 写代码 | 根据上下文编写或修改代码，直接操作项目源码 |
| **reflect** | 反思检查 | 检查代码变更是否符合需求，找出问题 |
| **judge** | 判断路由 | 根据反思报告决定流程走向（继续修改 or 通过） |
| **custom** | 自定义 | 用户自定义任何行为（暂停、用户输入、测试、部署……） |

用户也可以创建**自定义节点**，和系统节点完全平等，可以自由组合到流程中。

### Runner（执行器）

Runner 是底层的 AI 引擎，负责实际执行节点任务。目前支持：

| Runner | 引擎 | 安装 |
|--------|------|------|
| **cody** | Cody SDK（`cody-ai`） | `pip install codyflow[cody]` |
| **claude** | Claude Agent SDK | `pip install codyflow[claude]` |

Runner 可以**全局设置默认值**，也可以在**单个节点上覆盖**。比如讨论节点用 Claude（擅长分析），写代码节点用 Cody（工具链丰富）。

### Edge（连线）与条件路由

节点之间通过连线（Edge）连接。连线可以带条件：

```
discuss → learn → code → reflect → judge
                   ↑                  │
                   │  condition:      │ condition:
                   │  needs_fix       │ passed
                   └──────────────────┘    → END
```

判断节点（judge）通过 AI 分析来决定路由走向，不需要硬编码规则。

### 上下文传递

节点之间通过**文件系统**传递上下文：

- 所有节点产出的报告、总结文档存放在 `.codyflow/context/` 目录下
- 每个节点在执行时能看到整个 flow 的**全貌**（目标、节点地图、可用文件列表）
- 节点**自己决定**要读取哪些上下文文件（而不是由引擎把所有内容塞给它）
- 写代码节点**直接操作项目源码**，context 里只放总结报告

这个设计让 AI 有全局视野，同时省 token、更灵活。

## User Stories

### Story 1：标准开发流程

> 作为开发者，我希望 AI 能按照"讨论 → 学习 → 写代码 → 反思 → 修复"的流程自动完成一个功能开发，而不是我手动驱动每一步。

```bash
codyflow init my-feature
codyflow run my-feature.flow.yaml -i "给项目添加用户登录功能，支持 JWT"
```

Flow 自动执行：
1. **discuss**（交互）：和用户讨论需求细节，产出结论文档
2. **learn**：AI 自主学习项目代码结构
3. **code**：根据讨论结论和学习成果编写代码
4. **reflect**：检查代码是否符合需求
5. **judge**：判断是否需要继续修改
6. 如果需要修改 → 回到 code → 再反思 → 再判断（最多 N 轮）
7. 全部通过 → 结束

### Story 2：自定义流程

> 作为开发者，我希望能自己设计流程，比如加一个"测试节点"，或者在写代码前加一个"API 设计节点"。

```yaml
nodes:
  - id: discuss
    type: discuss
    interactive: true
    outputs: [discuss_output.md]

  - id: api_design
    type: custom
    prompt: "根据讨论结论设计 REST API 接口文档，包括路径、方法、请求体、响应体"
    outputs: [api_design.md]

  - id: code
    type: code
    outputs: [code_output.md]

  - id: test
    type: custom
    prompt: "为新增的代码编写单元测试，并运行测试确保全部通过"
    outputs: [test_output.md]

edges:
  - from: discuss
    to: api_design
  - from: api_design
    to: code
  - from: code
    to: test
  - from: test
    to: END
```

### Story 3：节点级 Runner 切换

> 作为开发者，我希望讨论环节用 Claude（思维更强），写代码环节用 Cody（工具更全）。

```yaml
runner: cody  # 全局默认

nodes:
  - id: discuss
    type: discuss
    runner: claude   # 这个节点用 Claude
    outputs: [discuss_output.md]

  - id: code
    type: code
    # 不指定 runner，使用全局默认的 cody
    outputs: [code_output.md]
```

### Story 4：断点恢复

> 作为开发者，如果 flow 执行到一半因为网络中断了，我希望能从断点继续，而不是重头开始。

```bash
# 中断了
codyflow resume my-feature.flow.yaml
# 从上次中断的节点继续执行
```

### Story 5：变量替换

> 作为开发者，我不想每次跑不同任务都改 YAML 文件。

```yaml
name: "feature-dev"
description: "为 {project_name} 添加 {feature_name}"
```

```bash
codyflow run feature-dev.flow.yaml \
  -v project_name="my-app" \
  -v feature_name="用户认证"
```

### Story 6：用户介入点

> 作为开发者，我希望在某些关键节点能暂停下来，让我确认后再继续。

```yaml
nodes:
  - id: code
    type: code
    outputs: [code_output.md]

  - id: user_review
    type: custom
    interactive: true
    prompt: "代码已写完，请查看变更内容。你有什么修改意见吗？"
    outputs: [review_feedback.md]

  - id: reflect
    type: reflect
    outputs: [reflect_output.md]

edges:
  - from: code
    to: user_review
  - from: user_review
    to: reflect
```

### Story 7：错误处理

> 作为开发者，如果某个节点执行失败，我希望能配置重试策略而不是整个流程崩掉。

```yaml
nodes:
  - id: code
    type: code
    error_strategy: retry  # retry | skip | fail
    max_retries: 3
    outputs: [code_output.md]

  - id: deploy
    type: custom
    error_strategy: fail   # 部署失败就直接停
    prompt: "部署到测试环境"
    outputs: [deploy_output.md]
```

## 技术架构

```
┌─────────────────────────────────────────────────────────┐
│                      CLI (click)                         │
│           init / run / resume 命令                       │
├─────────────────────────────────────────────────────────┤
│                   YAML Parser                            │
│        解析 flow.yaml → FlowDefinition                   │
│        支持变量替换 {var_name}                            │
├─────────────────────────────────────────────────────────┤
│               Flow Engine (LangGraph)                    │
│     StateGraph 图编排 | 条件路由 | 循环控制               │
│     SQLite Checkpoint 状态持久化 & 断点恢复               │
├──────────────────────┬──────────────────────────────────┤
│     Node System      │        Runner System              │
│  ┌────────────────┐  │  ┌──────────────────────────┐    │
│  │ discuss (交互)  │  │  │ Runner 抽象接口            │    │
│  │ learn           │  │  ├──────────────────────────┤    │
│  │ code            │  │  │ CodyRunner (cody-ai)     │    │
│  │ reflect         │  │  │ ClaudeRunner (claude-sdk) │    │
│  │ judge (路由)    │  │  │ 未来可扩展...              │    │
│  │ custom (自定义) │  │  └──────────────────────────┘    │
│  └────────────────┘  │                                   │
├──────────────────────┴──────────────────────────────────┤
│                  .codyflow/ 工作目录                      │
│     context/  上下文文件 | state.db 执行状态              │
└─────────────────────────────────────────────────────────┘
```

## 技术选型

| 组件 | 选型 | 原因 |
|------|------|------|
| 语言 | Python | Cody SDK 和 Claude SDK 都原生支持 |
| 流程编排 | LangGraph | 专为 AI Agent 设计，轻量，内置状态持久化 |
| 状态持久化 | SQLite (via LangGraph Checkpoint) | 零配置，支持断点恢复 |
| 上下文传递 | 文件系统 (.codyflow/context/) | 简单直观，AI Agent 可直接读取 |
| 流程定义 | YAML | 易读易写，支持变量替换 |
| CLI | Click + Rich | 标准 Python CLI 工具链 |

## 设计原则

1. **节点平等** — 自定义节点和系统节点使用相同的机制，没有特殊待遇
2. **AI 有全貌** — 每个节点看到整个 flow 的目标、节点地图和可用文件，自己决定读什么
3. **Runner 直接操作** — 写代码节点直接修改项目源码，context 只放报告
4. **会话独立** — 每个节点独立启动，通过文件传递上下文，避免 token 膨胀
5. **讨论需要人** — 讨论节点默认开启交互模式，全程用户参与
6. **可恢复** — 启动时把 running 状态的节点重置为待执行，从断点继续
