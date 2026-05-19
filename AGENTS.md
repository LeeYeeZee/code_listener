# Code Listener — Agent 开发指南

> 本文档面向 AI 编码代理。阅读本文后再修改代码。

## 1. 项目概述

**Code Listener** 是一个"代码→叙事切分→竖版短视频"的自动化引擎。

输入：任意代码仓库（如 LevelDB）  
输出：带讲解语音的竖版短视频（9:16），每页 = 一张 Mermaid 图 + 一段讲解文本

核心流程：
```
代码扫描 → 主题枚举(35个) → Storyboard大纲(35页) → 并发逐页生成(Mermaid+文本) → 渲染验证 → 视频合成
```

## 2. 目录结构

```
experiments/
├── main.py                    # 总控脚本（阶段一~四）
├── storyboard_engine.py       # 叙事引擎核心（LLM 生成 + 修复）
├── llm_client.py              # LLM 调用封装（OpenAI 兼容）
├── code_parser.py             # 代码仓库扫描与摘要
├── mermaid_sanitizer.py       # Mermaid 语法清理器
├── diagram_renderer.py        # Mermaid CLI 渲染（PNG）
├── tts_service.py             # TTS 语音合成（MiniMax / MiMo）
├── video_maker.py             # FFmpeg 视频操作
├── video_pipeline.py          # 视频合成管道（串行）
├── title_card.py              # Pillow 标题卡片生成
├── config.py                  # 全局配置（.env 加载）
├── requirements.txt           # Python 依赖
├── test_repo/                 # 默认测试仓库（FastAPI 项目）
├── leveldb/                   # LevelDB 源码（Git 子模块，已排除提交）
└── output/                    # 生成产物（已排除提交）
    ├── topics.json            # 阶段一输出：主题列表
    ├── storyboard.json        # 阶段二输出：Storyboard 大纲
    ├── result.json            # 阶段四输出：完整页面数据
    ├── report.md              # 人类可读报告
    └── temp_mermaid/          # 渲染临时 PNG
```

## 3. 关键约定

### 3.1 LLM 调用

- **模型**：默认 `deepseek-v4-pro`（阿里云百炼），OpenAI 兼容接口
- **timeout**：600s（推理模型响应慢）
- **max_tokens**：8192（reasoning_content 极长，必须给 content 留空间）
- **并发度**：`asyncio.Semaphore(5)`，同时最多 5 个 LLM 请求
- **重试**：指数退避（1s → 2s → 4s），最多 3 次

```python
# llm_client.py 用法
from llm_client import chat_completion

content = await chat_completion(
    messages=[...],
    temperature=0.3,
    response_format={"type": "json_object"},  # 要求返回 JSON
)
```

### 3.2 数据流约定

**阶段一**（主题枚举）：`generate_topics(code_summary, core_files)` → `topics.json`  
**阶段二**（Storyboard）：`generate_storyboard_from_topics(topics, code_summary, valid_files)` → `storyboard.json`  
**阶段三**（逐页生成）：`process_single_page(idx, page, ...)` × N（并发）→ `result.json`  
**阶段四**（视频合成）：`video_pipeline` 读取 `result.json` → 逐页串行合成 MP4

### 3.3 Mermaid 引号规则（极其重要）

节点标签内部**绝对禁止**出现未转义的双引号 `"`，这是渲染失败的头号原因。

- **Prompt 约束**：要求 LLM 用单引号 `'` 替代双引号
- **Sanitize 兜底**：`mermaid_sanitizer._escape_quotes()` 将 `"` → `#quot;`
- **Fix Prompt 对齐**：`fix_mermaid()` 的 prompt 必须与主 prompt 保持一致

### 3.4 Windows 平台

- 字体路径：`C:\Windows\Fonts\`（title_card.py）
- Mermaid CLI 编码：设置 `PYTHONIOENCODING=utf-8`，过滤 Unicode 私有区字符
- 使用 `asyncio.create_subprocess_shell` 而非 `create_subprocess_exec`

## 4. 编码规范

- **类型注解**：函数参数和返回值必须有类型注解
- **异步优先**：所有 IO 操作（LLM、文件、子进程）必须用 `async/await`
- **错误处理**：LLM 调用失败不阻断流程，降级为默认内容
- **配置外置**：所有可配置项放 `config.py`，从 `.env` 加载

## 5. 修改前必读

1. **修改 storyboard_engine.py** → 检查 `PAGE_SYSTEM_PROMPT` 和 `MERMAID_FIX_PROMPT` 是否一致
2. **修改 mermaid_sanitizer.py** → 添加新的 sanitize 规则后，必须跑 `test_mermaid.py` 验证
3. **修改 diagram_renderer.py** → 注意 Windows 编码问题，不要引入 `\` 路径转义 bug
4. **新增模块** → 在 `main.py` 中接入时保持两阶段流程的审阅暂停点

## 6. 已知限制

| 限制 | 说明 | 优先级 |
|------|------|--------|
| `_is_core_file()` 硬编码 LevelDB | 适配其他项目需修改过滤规则 | 高 |
| `video_pipeline.py` 串行无并发 | 35 页视频合成耗时较长 | 中 |
| TTS 未接入 | `.env` 无 `MIMO_API_KEY`，视频合成无法跑通 | 高 |
| `validate_mermaid()` 仅启发式 | 无法 100% 预判语法错误 | 低 |
