# Code Listener — 编码规范手册

## 1. Python 代码风格

### 1.1 基础规范

- **Python 版本**：3.12+
- **行长度**：120 字符（非 79/88）
- **引号**：字符串用双引号 `"`，docstring 用 `"""`
- **导入顺序**：标准库 → 第三方 → 本项目

```python
# 正确
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

import aiohttp
from dotenv import load_dotenv

from llm_client import chat_completion
import config

# 错误
from llm_client import chat_completion
import asyncio
import config
```

### 1.2 类型注解（强制）

所有函数参数和返回值必须有类型注解。

```python
# 正确
async def generate_page(
    course_title: str,
    narrative_mode: str,
    page: Dict[str, Any],
    total_pages: int,
) -> Dict[str, str]:
    ...

# 错误（无类型注解）
async def generate_page(course_title, narrative_mode, page, total_pages):
    ...
```

**常用类型别名**：
```python
from typing import Dict, Any, Optional

Page = Dict[str, Any]
Storyboard = Dict[str, Any]
FileContents = Dict[str, str]
```

### 1.3 异步规范

- 所有 IO 操作必须用 `async/await`
- 阻塞操作（如 subprocess）用 `asyncio.create_subprocess_shell`
- 同步文件读写用 `pathlib.Path` 的同步 API（文件操作通常很快）

```python
# 正确：LLM 调用是异步的
content = await chat_completion(messages=messages)

# 正确：子进程是异步的
proc = await asyncio.create_subprocess_shell(cmd, ...)

# 正确：文件读写用同步 API（足够快）
path.write_text(text, encoding="utf-8")
text = path.read_text(encoding="utf-8")
```

### 1.4 错误处理

- LLM 调用失败 → 重试 3 次，仍失败则降级，**不阻断流程**
- 文件操作失败 → 抛出异常，调用方决定是否捕获
- 子进程失败 → 检查 returncode，打印 stderr，返回 None

```python
# 正确：LLM 调用带降级
async def safe_generate_page(...) -> Dict[str, str]:
    try:
        return await generate_page(...)
    except Exception as e:
        print(f"[警告] 页面生成失败: {e}")
        return {
            "mermaid_diagram": "graph TD\n    A[生成失败] --> B[请检查日志]",
            "narration_text": f"本页内容生成时出错: {e}",
        }
```

## 2. Prompt 工程规范

### 2.1 Prompt 组织方式

所有 LLM Prompt 统一放在 `storyboard_engine.py` 的模块级常量中，命名规范：

```
{用途}_{类型}_PROMPT

例如：
PAGE_SYSTEM_PROMPT        # 单页生成的 system prompt
PAGE_USER_PROMPT_TEMPLATE # 单页生成的 user prompt（含占位符）
MERMAID_FIX_PROMPT        # Mermaid 修复 prompt
TOPICS_SYSTEM_PROMPT      # 主题枚举 system prompt
```

### 2.2 Prompt 内容规范

- **语言**：与目标受众一致（当前为中文）
- **格式约束**：用编号列表，每条约束前加 `【极其重要】` 表示最高优先级
- **Few-Shot**：至少提供 1 个合格示例 + 1 个反例
- **输出格式**：明确指定 JSON 结构，强调 `"不要包含 markdown 代码块标记"`

```python
# 正确
PAGE_SYSTEM_PROMPT = """你是一位技术讲师...

【输出格式】
你必须输出严格的 JSON 格式...

【图表布局要求：竖版短视频适配】
- 视频是竖版（9:16比例）...

【Mermaid 语法规范（必须严格遵守）】
1. ...
2. ...
6. 【极其重要】节点标签内部绝对禁止使用双引号 `"`...

【高质量输出示例】
...

【常见错误（切勿犯）】
...
"""
```

### 2.3 Prompt 一致性

**核心规则**：`MERMAID_FIX_PROMPT` 的引号约束必须与 `PAGE_SYSTEM_PROMPT` 完全一致。

```python
# PAGE_SYSTEM_PROMPT 中：
# "6. 【极其重要】节点标签内部绝对禁止使用双引号 `"`，如有需要请用单引号 `'` 替代"

# MERMAID_FIX_PROMPT 中必须对应：
# "1. 【极其重要】节点标签内部绝对禁止使用双引号 `"`，如有需要请用单引号 `'` 替代"
```

## 3. Mermaid 语法规范

### 3.1 节点标签

```mermaid
# 正确
A["BuildTable()"]:::core
B['hello "world"']:::core
C["Header(7B)<br>数据部分"]:::data

# 错误
A[BuildTable()]               # 含括号未包裹
B["hello \"world\""]         # 内部双引号未转义
C["hello "world""]           # 引号嵌套错误
```

### 3.2 连接线标签

```mermaid
# 正确
A -->|"找到且非删除, type=Value"| B

# 错误
A -->|"找到且非删除|se|type=Value"| B   # 多对竖线
```

### 3.3 节点 ID

```mermaid
# 正确
build_table --> generate_file
A1 --> B2

# 错误
构建表 --> 生成文件          # 中文 ID
Build-Table! --> File      # 特殊符号
```

### 3.4 配色规范

必须按语义角色着色，使用预定义的 classDef：

```mermaid
classDef core fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333
classDef data fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333
classDef external fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#333
classDef decision fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#333
classDef error fill:#FFEBEE,stroke:#E53935,stroke-width:2px,color:#333
classDef startEnd fill:#F5F5F5,stroke:#757575,stroke-width:2px,color:#333
```

**禁止**：自创类名、使用默认配色、不给节点着色。

## 4. 文件组织规范

### 4.1 模块职责单一

| 文件 | 职责 | 禁止做的事 |
|------|------|-----------|
| `main.py` | 总控流程编排 | 不包含 LLM prompt、不直接调用 HTTP |
| `storyboard_engine.py` | LLM 生成逻辑 | 不操作文件、不渲染 Mermaid |
| `llm_client.py` | HTTP 请求封装 | 不处理业务逻辑 |
| `mermaid_sanitizer.py` | 本地正则修复 | 不调用 LLM、不操作文件 |
| `diagram_renderer.py` | 子进程调用 mmdc | 不解析 Mermaid 语法 |
| `code_parser.py` | 文件扫描 | 不调用 LLM |
| `video_pipeline.py` | 视频编排 | 不直接生成 Mermaid 或 TTS |

### 4.2 配置集中

所有可配置项放 `config.py`，通过 `.env` 加载。

```python
# config.py
import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")

# 禁止在业务代码中直接读取 os.getenv
def some_function():
    # 错误
    api_key = os.getenv("LLM_API_KEY")
    
    # 正确
    api_key = config.LLM_API_KEY
```

## 5. 命名规范

### 5.1 函数命名

| 前缀 | 含义 | 示例 |
|------|------|------|
| `generate_` | LLM 生成 | `generate_topics()`, `generate_page()` |
| `render_` | 渲染/可视化 | `render_mermaid()` |
| `sanitize_` | 清理/修复 | `sanitize_mermaid()` |
| `fix_` | LLM 修复 | `fix_mermaid()` |
| `build_` | 构建/组装 | `build_code_summary()` |
| `process_` | 处理流程 | `process_single_page()` |

### 5.2 常量命名

```python
# 正确
PAGE_SYSTEM_PROMPT = "..."
MAX_RENDER_RETRIES = 2
LLM_SEMAPHORE = asyncio.Semaphore(5)

# 错误
pageSystemPrompt = "..."
maxRenderRetries = 2
```

## 6. 注释规范

### 6.1 Docstring

所有公共函数必须有 docstring，格式：

```python
async def generate_page(
    course_title: str,
    narrative_mode: str,
    page: Dict[str, Any],
    total_pages: int,
    previous_summary: str,
    next_title: str,
    file_contents: Dict[str, str],
) -> Dict[str, str]:
    """第2步：为单页生成 Mermaid 图 + 讲解文本。
    
    Args:
        course_title: 课程标题
        narrative_mode: 叙事模式 (layered|dataflow|scenario|deepdive)
        page: 当前页元数据（来自 Storyboard）
        total_pages: 总页数
        previous_summary: 前一页的 focus + cognitive_goal 摘要
        next_title: 下一页标题
        file_contents: 代码文件内容字典
    
    Returns:
        {"mermaid_diagram": str, "narration_text": str}
    """
```

### 6.2 行内注释

仅在逻辑复杂或非直观的地方添加注释。

```python
# 正确
# 用前一页的 focus + cognitive_goal 替代 narration 截断
# 这样不需要等前一页生成完毕，支持完全并发
previous_summary = f"上一页主题「{prev_focus}」：{prev_goal}"

# 错误（注释是废话）
# 设置 i 为 0
i = 0
```

## 7. 并发规范

### 7.1 Semaphore 使用

LLM 调用必须受 Semaphore 保护，其他操作不需要。

```python
# 正确：LLM 调用在 semaphore 内
async with LLM_SEMAPHORE:
    page_content = await generate_page(...)

# 正确：文件操作不需要 semaphore
output_path.write_text(json.dumps(data), encoding="utf-8")

# 正确：渲染验证不需要 semaphore
render_result = await render_mermaid(mermaid_text, temp_png)
```

### 7.2 并发安全

`process_single_page()` 的设计确保并发安全：
- `previous_summary` 从 `storyboard["pages"]` 读取（已完整生成，只读）
- `file_contents` 是只读字典
- 每个页面写入独立的临时文件

**禁止**：在 `process_single_page()` 中修改共享可变状态。
