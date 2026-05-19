# Code Listener — 测试手册

## 1. 测试策略

本项目采用**分层测试策略**：

| 层级 | 范围 | 目标 | 工具 |
|------|------|------|------|
| 单元测试 | 单个函数/模块 | 输入→输出正确性 | Python `unittest` |
| 集成测试 | 模块间交互 | LLM + Sanitize + Render 链路 | 端到端脚本 |
| 回归测试 | 全流程 | 从代码到视频的完整 pipeline | `main.py` |
| 人工审阅 | LLM 生成质量 | 叙事连贯性、图表可读性 | 肉眼检查 report.md |

## 2. 单元测试

### 2.1 mermaid_sanitizer.py 测试

**测试文件**：`experiments/test_mermaid.py`（已有）

**核心测试用例**：

```python
import unittest
from mermaid_sanitizer import sanitize_mermaid

class TestMermaidSanitizer(unittest.TestCase):
    
    def test_merge_broken_node(self):
        """测试合并被换行打断的节点"""
        raw = 'A[Finish()\n生成 SSTable]'
        result = sanitize_mermaid(raw)
        self.assertIn('A["Finish()<br>生成 SSTable"]', result)
    
    def test_escape_quotes(self):
        """测试双引号转义"""
        raw = 'A["hello "world""]'  # 内部双引号
        result = sanitize_mermaid(raw)
        self.assertNotIn('"world"', result)  # 残留双引号必须消失
        self.assertIn('#quot;', result)       # 应转为 HTML entity
    
    def test_stray_quotes(self):
        """测试残留双引号清理"""
        raw = 'delete["]']                    # 未闭合引号
        result = sanitize_mermaid(raw)
        self.assertNotIn('"]', result)
    
    def test_arrow_label_cleanup(self):
        """测试连接线标签清理"""
        raw = 'A -->|"a|b|c"| B'
        result = sanitize_mermaid(raw)
        self.assertIn('|"a, b, c"|', result)  # 多对竖线合并为逗号
    
    def test_subgraph_id_cleanup(self):
        """测试 subgraph ID 清理"""
        raw = 'subgraph build process'
        result = sanitize_mermaid(raw)
        self.assertIn('subgraph build_process', result)
    
    def test_br_format(self):
        """测试 <br> 格式统一"""
        raw = 'A["第一行<br/>第二行<br />第三行"]'
        result = sanitize_mermaid(raw)
        self.assertNotIn('<br/>', result)
        self.assertNotIn('<br />', result)
        self.assertIn('<br>', result)
```

**运行方式**：
```bash
cd experiments
python test_mermaid.py
```

### 2.2 diagram_renderer.py 测试

**测试目标**：Mermaid CLI 能正常渲染基本图表。

```python
import asyncio
import tempfile
from pathlib import Path
from diagram_renderer import render_mermaid

async def test_render_basic():
    mermaid = '''graph TD
        A["开始"]:::startEnd --> B{"判断"}:::decision
        B -->|"是"| C["处理"]:::core
        B -->|"否"| D["结束"]:::startEnd
        classDef core fill:#FFF3E0,stroke:#FB8C00
        classDef decision fill:#F3E5F5,stroke:#8E24AA
        classDef startEnd fill:#F5F5F5,stroke:#757575
    '''
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.png"
        result = await render_mermaid(mermaid, output)
        assert result is not None, "渲染失败"
        assert output.exists(), "输出文件未生成"
        assert output.stat().st_size > 0, "输出文件为空"
        print("✅ 基本渲染测试通过")

async def test_render_complex():
    """测试包含特殊字符的图表"""
    mermaid = '''graph TD
        A["BuildTable()"]:::core --> B["Header(7B)<br>数据部分"]:::data
        classDef core fill:#FFF3E0,stroke:#FB8C00
        classDef data fill:#E8F5E9,stroke:#43A047
    '''
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test_complex.png"
        result = await render_mermaid(mermaid, output)
        assert result is not None, "复杂图表渲染失败"
        print("✅ 复杂图表渲染测试通过")

# 运行
asyncio.run(test_render_basic())
asyncio.run(test_render_complex())
```

### 2.3 code_parser.py 测试

```python
import tempfile
from pathlib import Path
from code_parser import scan_directory

def test_scan_directory():
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件结构
        Path(tmpdir, "src", "main.py").write_text("print('hello')")
        Path(tmpdir, "src", "utils.py").write_text("def helper(): pass")
        Path(tmpdir, "tests", "test_main.py").write_text("def test(): pass")  # 应被过滤
        Path(tmpdir, ".hidden.py").write_text("secret")  # 应被过滤
        
        file_tree, file_contents = scan_directory(tmpdir)
        
        assert "src/main.py" in file_tree
        assert "src/utils.py" in file_tree
        assert "tests/test_main.py" not in file_tree  # _test. 被过滤
        assert ".hidden.py" not in file_tree  # 隐藏文件被过滤
        assert len(file_contents) == 2
        print("✅ 目录扫描测试通过")
```

## 3. 集成测试

### 3.1 LLM + Sanitize + Render 链路

**测试文件**：`experiments/test_api.py`（已有）

```python
async def test_llm_to_render_pipeline():
    """测试从 LLM 生成到渲染的完整链路"""
    from storyboard_engine import generate_page
    from mermaid_sanitizer import sanitize_mermaid
    from diagram_renderer import render_mermaid
    import tempfile
    
    page = {
        "page_index": 0,
        "title": "测试页",
        "focus": "测试 Mermaid 渲染",
        "cognitive_goal": "验证端到端链路",
        "scope_files": [],
    }
    
    # 1. LLM 生成
    content = await generate_page(
        course_title="测试课程",
        narrative_mode="layered",
        page=page,
        total_pages=1,
        previous_summary="",
        next_title="",
        file_contents={},
    )
    
    # 2. Sanitize
    mermaid = sanitize_mermaid(content["mermaid_diagram"])
    
    # 3. Render
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.png"
        result = await render_mermaid(mermaid, output)
        assert result is not None, f"渲染失败，mermaid:\n{mermaid}"
        print("✅ LLM→Sanitize→Render 链路测试通过")
```

### 3.2 TTS 测试

```python
async def test_tts():
    """测试 TTS 合成"""
    from tts_service import synthesize_speech
    import tempfile
    
    text = "这是一个测试语音合成的示例文本。"
    with tempfile.TemporaryDirectory() as tmpdir:
        output = Path(tmpdir) / "test.mp3"
        result = await synthesize_speech(text, output)
        assert result is not None, "TTS 失败"
        assert output.exists(), "音频文件未生成"
        assert output.stat().st_size > 1000, "音频文件过小"
        print("✅ TTS 测试通过")
```

## 4. 回归测试（全流程）

### 4.1 快速回归（test_repo）

```bash
cd experiments
python main.py test_repo
```

**预期结果**：
- 阶段一：生成主题列表（数量 > 0）
- 阶段二：生成 Storyboard（总页数 > 0）
- 阶段三：所有页面渲染通过（无降级）
- 输出：`result.json`、`report.md` 正常生成

### 4.2 完整回归（LevelDB）

```bash
cd experiments
python main.py leveldb
```

**预期结果**：
- 阶段一：生成 30~40 个主题
- 阶段二：Storyboard 总页数与主题数接近
- 阶段三：渲染通过率 > 90%
- 降级页面通过 `regenerate_failed_pages.py` 修复后 100% 通过

## 5. 人工审阅检查清单

### 5.1 Storyboard 质量

- [ ] 第 1 页是宏观概览，不陷入细节
- [ ] 每页 focus 明确，15 字以内
- [ ] 页与页之间有 depends_on 依赖链
- [ ] scope_files 精确到实际存在的文件路径

### 5.2 Mermaid 图表质量

- [ ] 使用 `graph TD`（自上而下）
- [ ] 节点数量 6~14 个，不拥挤
- [ ] 所有节点有 classDef 着色
- [ ] 节点标签不含未转义的双引号
- [ ] 竖版适配（高度 > 宽度）

### 5.3 Narration 质量

- [ ] 三段式结构：承接 + 主体 + 收尾
- [ ] 无"如图所示"等无效表述
- [ ] 严格围绕当前页 title 和 focus
- [ ] 口语化，每句不超过 25 字

## 6. 持续集成建议

```yaml
# .github/workflows/ci.yml（建议添加）
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r experiments/requirements.txt
      - run: cd experiments && python test_mermaid.py
      - run: cd experiments && python test_api.py
      - run: cd experiments && python main.py test_repo
```

## 7. 调试技巧

### 7.1 LLM 输出调试

当 LLM 返回异常时，临时修改 `llm_client.py` 打印完整响应：

```python
# 在 llm_client.py 中临时添加
data = await resp.json()
print(f"[LLM RAW] {json.dumps(data, ensure_ascii=False)[:2000]}")
return data["choices"][0]["message"]["content"]
```

### 7.2 Mermaid 渲染调试

渲染失败时，保留临时 `.mmd` 文件：

```python
# 在 diagram_renderer.py 中注释掉 finally 块的清理逻辑
# finally:
#     if input_file.exists():
#         input_file.unlink()
```

然后手动运行：
```bash
mmdc -i temp.mmd -o test.png -b #ffffff -w 1080 -H 1920
```

### 7.3 并发调试

将 `LLM_SEMAPHORE` 改为 1，串行执行：

```python
LLM_SEMAPHORE = asyncio.Semaphore(1)  # 临时改为串行，方便定位问题
```
