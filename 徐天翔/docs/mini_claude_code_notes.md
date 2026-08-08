# Mini Claude Code 源码分析笔记

> 基于 [learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) v0–v4 源码分析
> 5 个版本，~1100 行，每个版本新增一个核心概念

---

## 1. 用户指令如何解析为工程任务

### 1.1 全景流程

```
用户输入
   │
   ▼
┌─────────────────────────────────────────────────┐
│ 1. 消息收集                                      │
│    - 用户输入 → {"role": "user", "content": Q}  │
│    - 可选注入提醒（Todo/技能提示）                │
└──────────┬──────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────┐
│ 2. 模型推理（含工具注册）                         │
│    - 系统提示（约束行为）                         │
│    - 消息历史（上下文）                           │
│    - 工具定义（TOOLS 数组 → JSON Schema）         │
│    - 模型输出：文本 + tool_use 块                 │
└──────────┬──────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────┐
│ 3. 工具执行循环                                   │
│    while stop_reason == "tool_use":              │
│      for tc in tool_calls:                       │
│        output = execute_tool(tc.name, tc.input)  │
│        results.append(tool_result)               │
│      messages.append(results)                    │
│      response = model(messages, tools)           │
└──────────┬──────────────────────────────────────┘
           ▼
┌─────────────────────────────────────────────────┐
│ 4. 任务完成                                       │
│    stop_reason != "tool_use" → 输出最终文本       │
└─────────────────────────────────────────────────┘
```

### 1.2 各版本的解析深度

| 版本 | 解析方式 | 粒度 |
|------|----------|------|
| **v0** | 模型自主理解，1 个 bash 工具，递归自调用 | 最粗 |
| **v1** | 4 工具 + 系统提示约束行为模式 | 中等 |
| **v2** | + TodoWrite 工具，强制可见计划 | 细粒度 |
| **v3** | + Task 工具，子代理隔离探索/编码/规划 | 任务分解 |
| **v4** | + Skill 工具，按需加载领域知识 | 知识注入 |

### 1.3 关键机制：计划可见性（v2）

`TodoWrite` 工具是用户指令→工程任务的核心桥梁：

```python
# v2_todo_agent.py: TodoManager.update()
# 模型发送完整任务列表（非 diff），服务端验证：
#   - 最多 20 项
#   - 只有一个 in_progress
#   - 每项必须含 content/status/activeForm
# 渲染为可见清单： [x] 完成  [>] 进行中  [ ] 待办
```

**为什么有效**：计划从 "模型脑子里" 变成 "对话上下文中的可见状态"——模型看到它、维护它、用户看到它。

---

## 2. 工具调用的完整流程

### 2.1 架构层次

```
┌──────────────────────────────────────────┐
│              用户 REPL                     │
│  input("You: ") → history.append()        │
│  → agent_loop(history)                    │
├──────────────────────────────────────────┤
│            Agent Loop (v1–v4)              │
│  while True:                              │
│    response = client.messages.create(...) │
│    if stop_reason != "tool_use": break    │
│    results = execute_tools(response)       │
│    messages.append(results)               │
├──────────────────────────────────────────┤
│         execute_tool() 分发器              │
│  name == "bash"     → run_bash()          │
│  name == "read_file" → run_read()         │
│  name == "write_file" → run_write()       │
│  name == "edit_file" → run_edit()         │
│  name == "TodoWrite" → run_todo()         │
│  name == "Task"     → run_task() (v3)     │
│  name == "Skill"    → run_skill() (v4)    │
├──────────────────────────────────────────┤
│          具体工具实现                        │
│  subprocess.run / Path.read_text / ...    │
└──────────────────────────────────────────┘
```

### 2.2 Tools 定义（JSON Schema 模式）

每个工具包含：
```python
{
    "name": "edit_file",           # 唯一标识
    "description": "Replace exact text in file.",  # 向模型描述功能
    "input_schema": {               # JSON Schema 约束参数
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
        },
        "required": ["path", "old_text", "new_text"],
    },
}
```

**核心洞见**：工具描述 + Schema 是模型的 "API 文档"——模型靠它理解何时调用、传什么参数。

### 2.3 工具执行细节

**bash 工具**（v0–v4 通用模式）：
```python
# 安全过滤 → subprocess.run(..., shell=True, timeout=60) → 截断 50KB
def run_bash(command: str) -> str:
    dangerous = ["rm -rf /", "sudo", "shutdown"]
    if any(d in cmd for d in dangerous):
        return "Error: Dangerous command blocked"
    result = subprocess.run(command, shell=True, cwd=WORKDIR,
                            capture_output=True, text=True, timeout=60)
    return (result.stdout + result.stderr)[:50000]
```

**read/write/edit 文件工具**：基于 `Path()` 的安全路径解析防止目录穿越：
```python
def safe_path(p: str) -> Path:
    path = (WORKDIR / p).resolve()
    if not path.is_relative_to(WORKDIR):
        raise ValueError(f"Path escapes workspace: {p}")
    return path
```

### 2.4 子代理调用流程（v3）

```
主代理调用 Task(explore, "寻找所有 auth 文件")
   │
   ▼
run_task():
   │
   ├── 1. 根据 agent_type("explore") 获取配置
   │      只允许 bash + read_file（只读）
   │
   ├── 2. 创建 ISOLATED 消息历史
   │      sub_messages = [{role: "user", content: prompt}]
   │      （不继承父对话！）
   │
   ├── 3. 独立 agent 循环
   │      while stop_reason == "tool_use":
   │          调用模型(子上下文, 子工具)
   │          执行工具
   │
   ├── 4. 返回 ONLY 最终文本
   │      return block.text（干净摘要）
   │
   ▼
主代理收到："Auth 在 src/auth/login.py, src/auth/middleware.py"
```

### 2.5 技能注入流程（v4）

```
用户："帮我处理一个 PDF"

模型匹配 -> 调用 Skill("pdf")
   │
   ▼
run_skill():
   │
   ├── 1. SkillLoader 扫描 skills/<name>/SKILL.md
   │
   ├── 2. 解析 YAML 前置元数据 + Markdown 正文
   │
   ├── 3. 作为 tool_result 返回（不是修改 system prompt！）
   │      <skill-loaded name="pdf">
   │      # PDF Processing Skill
   │      ## Reading PDFs
   │      Use pdftotext for quick extraction: ...
   │      </skill-loaded>
   │
   ▼
模型："明白了，我用 pdftotext 提取文本"
```

**为什么是 `tool_result` 而不是 system prompt？** 修改 system prompt 会使上下文缓存失效（20–50 倍成本增加）；追加 tool_result 只影响末尾，前缀缓存命中。

---

## 3. 如何向现有框架添加自定义工具

### 3.1 四步法（基于 v4 架构）

```
Step 1: 定义 JSON Schema
Step 2: 实现处理函数
Step 3: 注册到 execute_tool() 分发器
Step 4: 更新系统提示（可选）
```

### 3.2 示例：添加 `web_search` 工具

**Step 1 — 定义 Schema**（添加到 `ALL_TOOLS` 或 `BASE_TOOLS`）：

```python
{
    "name": "web_search",
    "description": "Search the web for current information. Use when you need up-to-date data.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query string"
            },
        },
        "required": ["query"],
    },
}
```

**Step 2 — 实现处理函数**：

```python
def run_web_search(query: str) -> str:
    """调用搜索 API 返回结果摘要"""
    import requests
    try:
        response = requests.get(
            f"https://api.example.com/search?q={query}",
            timeout=10
        )
        results = response.json()
        # 格式化为简洁摘要
        return "\n".join(
            f"{r['title']}: {r['snippet']}"
            for r in results[:5]
        )[:50000]
    except Exception as e:
        return f"Search error: {e}"
```

**Step 3 — 注册分发**：

```python
def execute_tool(name: str, args: dict) -> str:
    if name == "bash":
        return run_bash(args["command"])
    # ... 已有工具 ...
    if name == "web_search":        # ← 新增
        return run_web_search(args["query"])  # ← 新增
    return f"Unknown tool: {name}"
```

**Step 4 — 更新系统提示**（可选，帮助模型理解何时使用）：

```python
SYSTEM = """...
工具:
- bash: 运行命令
- web_search: 搜索网络（用于获取最新信息）
- ..."""
```

### 3.3 添加复杂工具的模式

| 类型 | 模式 | 示例 |
|------|------|------|
| **同步执行** | 函数调用后返回字符串 | web_search, calculator |
| **异步/长耗时** | 后台任务 + 进度通知 | docker build, pip install |
| **子代理** | 注册到 AGENT_TYPES + Task 工具 | explore, plan |
| **知识注入** | 添加 SKILL.md + Skill 工具 | pdf, mcp-builder |

### 3.4 子代理类型注册（v3 模式）

```python
AGENT_TYPES["security_review"] = {
    "description": "Security-focused code review agent",
    "tools": ["bash", "read_file"],  # 只读
    "prompt": "You are a security reviewer. Analyze code for vulnerabilities...",
}
```

无需改动工具循环——只加配置。get_tools_for_agent("security_review") 自动返回对应工具集。

### 3.5 技能目录注册（v4 模式）

```
skills/
  my-domain/
    SKILL.md          # YAML 前置元数据 + Markdown 指令
    scripts/           # 辅助脚本
    references/        # 参考文档
```

SKILL.md 格式：

```markdown
---
name: my-domain
description: Handle my-domain-specific tasks
---

# My Domain Skill

## Processing

Follow these steps:
1. Step one...
2. Step two...
```

SkillLoader 自动扫描 skills/ 目录，注册到系统提示。模型通过 `Skill("my-domain")` 按需加载。

---

## 4. 确定 AI 编程助手方案：KimiCode + MCP 服务器

### 4.1 方案架构

```
┌──────────────────┐     MCP 协议（JSON-RPC over stdio/HTTP）
│   KimiCode CLI   │◄──────────────────────────────────►┌──────────────────┐
│  (MCP Host)      │     初始化 / tools/list              │  MCP Server      │
│                  │     / tools/call                    │  (Python SDK)    │
│  ┌────────────┐  │                                     │                  │
│  │ LLM Engine │  │                                     │  ┌────────────┐  │
│  │ (Kimi)     │  │                                     │  │ pyserial   │  │
│  └────────────┘  │                                     │  │ → UART     │  │
│         │        │                                     │  │ → MicroPy  │  │
│         ▼        │                                     │  └────────────┘  │
│  工具调用决策     │                                     └──────────────────┘
└──────────────────┘                                              │
                                                                   ▼
                                                           ┌──────────────────┐
                                                           │  嵌入式设备        │
                                                           │  MicroPython     │
                                                           │  Raw REPL        │
                                                           └──────────────────┘
```

### 4.2 优势

| 层面 | 优势 |
|------|------|
| **KimiCode** | 国产大模型，中文理解和代码生成能力强，API 成本低 |
| **MCP 协议** | 标准化工具接口，可接入任意 MCP 服务器，生态丰富 |
| **分离架构** | LLM + 工具解耦，工具可单独开发/测试/部署 |
| **嵌入式目标** | MCP Server 通过 pyserial 与 MicroPython REPL 通信，屏蔽串口细节 |

### 4.3 与本项目的关系

本项目 v3 的 `Task` 工具和 v4 的 `Skill` 机制直接对应 MCP 的设计哲学：

| Mini Claude Code | MCP | 类比 |
|------------------|-----|------|
| execute_tool() 分发 | tools/call | 统一工具调用入口 |
| AGENT_TYPES / Task | 不同 MCP Server | 服务隔离 |
| Skill / SKILL.md | Resources + Prompts | 上下文注入 |
| tool_result → messages | 标准化 Content 类型 | 结果回传 |

---

## 附录：代码结构映射

```
文件                         核心概念
─────────────────────────────────────────────────
v0_bash_agent_mini.py     Bash 即一切（16 行极简版）
v0_bash_agent.py          Bash 即一切（45 行递归版）
v1_basic_agent.py         Model as Agent（4 工具 + 主循环）
v2_todo_agent.py          结构化规划（+ TodoManager）
v3_subagent.py            子代理机制（+ AgentType Registry + Task）
v4_skills_agent.py        Skills 机制（+ SkillLoader + SKILL.md）
skills/                   技能目录（pdf/mcp-builder/code-review/agent-builder）
docs/                     机制详解文档（中英双语）
```

关键函数追踪：

```python
# 入口
agent_loop(history)         # v1-v4 核心循环

# 工具定义
TOOLS / BASE_TOOLS          # JSON Schema 数组
ALL_TOOLS = BASE_TOOLS + [TASK_TOOL, SKILL_TOOL]  # v4 完整工具集

# 分发器
execute_tool(name, args)    # 单一入口 → 具体实现

# 子代理
run_task(desc, prompt, type)  # 隔离上下文 + 独立循环

# 技能加载
run_skill(skill_name)         # 读取 SKILL.md → tool_result 注入
```
