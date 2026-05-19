# CodeWiki 叙事引擎 — 架构设计文档

## 1. 系统目标

将任意代码仓库自动转换为一系列带讲解的竖版短视频（1080×1920，9:16）。

每个视频页 = 一张 Mermaid 架构/流程/数据结构图 + 一段 30~120 秒的语音讲解。

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              输入层 (Input)                                  │
│                    任意代码仓库目录 (Git repo / 本地目录)                      │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ file_tree, file_contents
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           预处理层 (Preprocessing)                           │
│  code_parser.py: 扫描目录 → 过滤非代码文件 → 按优先级排序 → 截断提取内容       │
│  输出: file_tree[List[str]], file_contents[Dict[str, str]], code_summary     │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ code_summary, core_files
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          叙事引擎层 (Narrative Engine)                        │
│  storyboard_engine.py                                                        │
│  ├─ 阶段一: generate_topics()          → topics.json (主题列表)              │
│  ├─ 阶段二: generate_storyboard_from_topics() → storyboard.json (35页大纲)  │
│  ├─ 阶段三: generate_page()            → 单页 Mermaid + narration           │
│  └─ 修复:   fix_mermaid()              → LLM 自动修复语法错误               │
│                                                                              │
│  mermaid_sanitizer.py: 本地正则修复常见语法错误（引号、换行、连接线等）       │
│  diagram_renderer.py:  mmdc 渲染 Mermaid → PNG (1080×1920)                 │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │ result.json
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          视频合成层 (Video Pipeline)                          │
│  video_pipeline.py                                                           │
│  ├─ render_mermaid()     → PNG (每页一张图)                                  │
│  ├─ synthesize_speech()  → MP3 (每页一段语音)                                │
│  ├─ make_video()         → MP4 (图+语音合成)                                 │
│  ├─ generate_title_card()→ PNG (标题卡)                                      │
│  ├─ make_title_video()   → MP4 (标题静音视频)                                │
│  └─ concat_videos()      → final.mp4 (标题+内容拼接)                         │
│                                                                              │
│  video_maker.py:   FFmpeg 操作封装                                           │
│  tts_service.py:   MiniMax / MiMo TTS 封装                                   │
│  title_card.py:    Pillow 生成极简标题卡片                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 3. 核心模块设计

### 3.1 code_parser.py

**职责**：代码仓库的扫描与摘要。

```python
def scan_directory(repo_path: str) -> tuple[list[str], dict[str, str]]:
    """扫描目录，返回文件列表和内容字典。"""

def build_code_summary(file_tree: list[str], file_contents: dict[str, str]) -> str:
    """构建代码摘要（用于 LLM prompt）。"""
```

**过滤规则**：
- 排除：`_test.`, `_tests.`, 以 `.` 开头的隐藏文件
- 优先级排序：`["db", "table", "util", "include"]` 优先
- 内容截断：超过 8000 字符的文件只保留前 8000 字符 + `"... [truncated] ..."`

**TODO**：硬编码的 `priority_dirs` 和 `_is_core_file()` 需要通用化。

### 3.2 storyboard_engine.py

**职责**：整个叙事流程的 LLM 生成核心。

**两阶段拆分设计**：

```
阶段一 (Topic Enumeration)
  输入: code_summary + core_files
  LLM:  遍历所有核心文件，枚举技术主题
  输出: topics = [{topic_id, title, focus, scope_files, rationale}]
  控制: 人工审阅点 — topics.json 生成后脚本暂停，允许手动增删主题

阶段二 (Storyboard Generation)
  输入: topics + code_summary
  LLM:  基于主题列表生成完整 Storyboard 大纲
  输出: storyboard = {title, narrative_mode, total_pages, pages[...]}
  约束: 每页必须有 focus, cognitive_goal, scope_files, instruction, depends_on

阶段三 (Page Generation) — 并发执行
  输入: storyboard.pages[i]
  LLM:  为单页生成 Mermaid 图 + narration 文本
  输出: page_content = {mermaid_diagram, narration_text}
  并发: asyncio.gather() + Semaphore(5)
```

**Few-Shot 设计**：
- 3 个高质量 Page 示例（架构/流程/数据结构）
- 5 个 Mermaid 反例（引号、换行、连接线标签等）
- 4 个 narration 反例（看图表述、无承接、偏离主题、无收尾）

### 3.3 mermaid_sanitizer.py

**职责**：本地正则修复 LLM 生成的 Mermaid 语法错误。

**修复策略（按优先级）**：

| 优先级 | 问题 | 修复方法 |
|--------|------|----------|
| P0 | 节点被 `\n` 打断 | 合并行，用 `<br>` 替换换行 |
| P1 | 节点标签含特殊字符未包裹 | 用 `["..."]` 包裹，内部 `"` → `#quot;` |
| P1 | 节点标签含残留双引号 | `delete["]` → `delete[']` |
| P2 | 连接线标签有多对 `\|` | `\|a\|b\|` → `\|a, b\|` |
| P2 | subgraph ID 含空格 | `subgraph build process` → `subgraph build_process` |
| P3 | 多余空行 | 压缩 `
{3,}` → `

` |

**关键决策**：`#quot;` vs `"`  
- Mermaid CLI v11.15.0 支持 HTML entity `#quot;`，不支持转义 `"`  
- 因此 sanitize 时将 `"` 替换为 `#quot;`，而非 `\"`

### 3.4 diagram_renderer.py

**职责**：调用 Mermaid CLI 将文本渲染为 PNG。

```python
async def render_mermaid(mermaid_text, output_path, width=1080, height=1920) -> Path | None
```

**竖版适配**：
- 分辨率：1080×1920（竖版 9:16）
- 背景色：纯白 `#ffffff`
- 优先使用 `graph TD`（自上而下布局）

**Windows 编码处理**：
- 设置 `PYTHONIOENCODING=utf-8`
- 过滤 Unicode 私有区字符（`\ufb02` → `fi`）
- 使用临时 `.mmd` 文件输入，避免 stdin 编码问题

### 3.5 video_pipeline.py

**职责**：将 `result.json` 转换为最终视频。

**单页处理流程**：
```
sanitize_mermaid() → render_mermaid() → PNG
synthesize_speech() → MP3
make_video(PNG, MP3) → content.mp4
generate_title_card() → title.png
make_title_video(title.png) → title.mp4
concat_videos([title.mp4, content.mp4]) → page_{i}.mp4
```

**当前限制**：逐页串行处理，无并发优化。

## 4. 数据模型

### 4.1 Topic

```json
{
  "topic_id": "T01",
  "title": "数据库架构全景",
  "focus": "LevelDB 的分布式架构、接口层、内部模块",
  "scope_files": ["include/leveldb/db.h", "include/leveldb/options.h"],
  "rationale": "这些文件定义了公共接口，是理解 LevelDB 的入口"
}
```

### 4.2 Storyboard Page

```json
{
  "page_index": 0,
  "title": "数据库架构全景",
  "focus": "架构全景与读写路径",
  "cognitive_goal": "理解 LevelDB 为什么采用 LSM-Tree 架构",
  "scope_files": ["include/leveldb/db.h", "db/db_impl.cc"],
  "instruction": "画出 DB 接口与 MemTable、SSTable、WAL 的关系",
  "depends_on": []
}
```

### 4.3 Page Content

```json
{
  "mermaid_diagram": "graph TD\n    A[\"客户端请求\"]:::external --> B{\"认证通过?\"}:::decision\n    ...",
  "narration_text": "上一页我们了解了...，现在来看..."
}
```

## 5. 错误处理与降级策略

| 层级 | 失败场景 | 处理策略 |
|------|----------|----------|
| LLM 调用 | timeout / rate limit | 指数退避重试 3 次 |
| 内容生成 | narration 为空 / mermaid < 5 行 | 自动重试生成 1 次 |
| Mermaid 渲染 | 语法错误 | LLM fix_mermaid() 修复，最多 2 次 |
| Mermaid 渲染 | 修复后仍失败 | 降级为 `graph TD\n    A[图表渲染失败] --> B[...]` |
| 页面处理 | 全流程异常 | 降级页面，记录异常信息，不阻断其他页面 |
| TTS 合成 | API 失败 | 返回 None，跳过语音，保留图片 |
| 视频合成 | FFmpeg 失败 | 返回 None，记录错误日志 |

## 6. 外部依赖与配置

### 6.1 必需依赖

| 组件 | 安装方式 | 验证命令 |
|------|----------|----------|
| Python 3.12 | - | `python --version` |
| Mermaid CLI | `npm install -g @mermaid-js/mermaid-cli` | `mmdc --version` |
| FFmpeg | 下载并加入 PATH | `ffmpeg -version` |

### 6.2 Python 包

```
aiohttp>=3.9
Pillow>=10.0
python-dotenv>=1.0
```

### 6.3 环境变量 (.env)

```bash
# LLM (必需)
LLM_API_KEY=your_key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=deepseek-v4-pro

# TTS — MiniMax (可选)
MINIMAX_API_KEY=your_key
MINIMAX_API_URL=https://api.minimax.chat/v1/t2a_v2
MINIMAX_VOICE_ID= male-qn-qingse

# TTS — MiMo (可选)
MIMO_API_KEY=your_key
MIMO_API_URL=https://api.example.com/mimo
MIMO_VOICE_ID=default
```

## 7. 扩展点

| 扩展方向 | 修改文件 | 说明 |
|----------|----------|------|
| 支持新语言 | `code_parser.py` | 扩展文件过滤和优先级规则 |
| 新叙事模式 | `storyboard_engine.py` | 在 Prompt 中增加 `narrative_mode` 选项 |
| 新 TTS 供应商 | `tts_service.py` | 实现 `synthesize_speech()` 接口 |
| 新视频风格 | `title_card.py` | 修改标题卡片设计 |
| 视频并发合成 | `video_pipeline.py` | 借鉴 `main.py` 的 `asyncio.gather` 模式 |
