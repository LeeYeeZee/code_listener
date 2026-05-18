"""
Mermaid 语法清理器：自动修复 LLM 生成的常见语法错误

核心策略（按优先级）：
1. 合并被 \n 打断的节点定义（最顽固的问题）
2. 修复节点标签中的特殊字符
3. 修复连接线标签中的 markdown 污染
"""
import re

# 需要触发引号包裹的特殊字符
SPECIAL_CHARS = '()[]{}<>;"|'


def _needs_quotes(text: str) -> bool:
    """判断节点标签是否需要用引号包裹。"""
    return any(c in text for c in SPECIAL_CHARS) or '<br' in text


def _escape_quotes(text: str) -> str:
    """将标签中的双引号替换为 #quot;（Mermaid 支持的 HTML entity）。"""
    return text.replace('"', '#quot;')


def _has_unescaped_quotes(text: str) -> bool:
    """检测文本中是否存在未正确转义的双引号（即不在 #quot; 中的双引号）。"""
    # 简单检查：替换所有 #quot; 占位符后，是否还有剩余的双引号
    temp = text.replace('#quot;', '')
    return '"' in temp


def _fix_node_content(match: re.Match) -> str:
    """通用节点内容修复：包裹在引号中。"""
    wrapper_open = match.group(1)  # [, {, (
    inner = match.group(2)
    wrapper_close = match.group(3)  # ], }, )
    
    if _needs_quotes(inner):
        inner = _escape_quotes(inner)
        # 返回时用方括号+引号包裹（最兼容）
        return f'["{inner}"]'
    return match.group(0)


def sanitize_mermaid(text: str) -> str:
    """
    清理 Mermaid 语法，修复 LLM 生成的常见错误。
    """
    if not text:
        return text

    # 统一换行符
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # 0. 解码 HTML entity（LLM 有时会把 < > & 编码）
    text = text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&").replace("&quot;", '"')
    
    # 0.5 修复双重转义：\#quot; -> #quot;
    text = text.replace("\\#quot;", "#quot;")

    # 1. 修复 <br/> -> <br>（Mermaid v10+ 只支持 <br>）
    text = text.replace("<br/>", "<br>").replace("<br />", "<br>")

    # 2. 【核心修复】合并被 \n 打断的节点定义
    # LLM 经常在节点标签内部插入换行，如:
    #   tb --> finish[Finish()
    #   生成 SSTable 文件]
    # 需要合并为:
    #   tb --> finish[Finish()<br>生成 SSTable 文件]
    lines = text.splitlines()
    merged_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 检测当前行是否是节点定义的"上半身"（有 opening bracket 但没有 closing bracket）
        # 且不是 subgraph 等声明行
        if not stripped.startswith("subgraph") and not stripped.startswith("graph") and not stripped.startswith("flowchart"):
            # 检查是否有未闭合的 [ { (
            open_sq = line.count('[')
            close_sq = line.count(']')
            open_cu = line.count('{')
            close_cu = line.count('}')
            open_pa = line.count('(')
            close_pa = line.count(')')
            
            # 如果当前行有 opening 但没有对应的 closing，尝试和下一行合并
            if (open_sq > close_sq or open_cu > close_cu or open_pa > close_pa) and i + 1 < len(lines):
                next_line = lines[i + 1]
                # 合并，用 <br> 替换换行
                combined = line + "<br>" + next_line
                
                # 检查合并后是否闭合了
                if (combined.count('[') >= combined.count(']') and 
                    combined.count('{') >= combined.count('}') and
                    combined.count('(') >= combined.count(')')):
                    merged_lines.append(combined)
                    i += 2
                    continue
        
        merged_lines.append(line)
        i += 1
    
    text = "\n".join(merged_lines)

    # 3. 确保 graph/flowchart 声明后严格换行
    text = re.sub(
        r'^(graph|flowchart)\s+([A-Za-z]+)\s+(?=[A-Za-z0-9])',
        r'\1 \2\n    ',
        text,
        flags=re.MULTILINE,
    )

    # 4. 修复节点定义中的特殊字符
    # 使用3个捕获组: (wrapper_open)(inner)(wrapper_close)
    text = re.sub(r'(\[)([^\]]+)(\])', _fix_node_content, text)
    text = re.sub(r'(\{)([^\}]+)(\})', _fix_node_content, text)
    text = re.sub(r'(\()([^\)]+)(\))', _fix_node_content, text)
    
    # 4.5 【关键修复】检测并移除节点标签中残留的双引号
    # LLM 有时会在节点标签内部生成未转义的双引号，如 delete["]、inputs[2"] 等
    # 这些会导致 Mermaid 解析器报错
    def _remove_stray_quotes(match: re.Match) -> str:
        inner = match.group(1)
        # 将残留的双引号替换为单引号
        inner_clean = inner.replace('"', "'")
        return f'["{inner_clean}"]'
    
    # 匹配 A["..."] 格式中内部仍有双引号的情况
    text = re.sub(r'\["([^"]*"[^"]*)"\]', _remove_stray_quotes, text)

    # 5. 修复连接线标签中的 markdown 污染
    # LLM 经常生成 -->|标签|se|type=Value| 这种格式
    # 需要把多余的 | 合并为一个标签
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if '-->|' in line:
            # 找到 -->| 的位置
            arrow_pos = line.find('-->|')
            # 找到箭头后面的第一个节点定义（如 K[、L[、M{ 等）
            remainder = line[arrow_pos + 3:]  # 跳过 '-->'
            # remainder 现在以 |标签|...| 节点ID[...] 开头
            # 找到节点定义开始的位置（非空格字符，通常是字母）
            node_match = re.search(r'\s+[A-Za-z0-9_]+\s*[\[\{\(]', remainder)
            if node_match:
                label_part = remainder[:node_match.start()].strip()
                node_part = remainder[node_match.start():]
                # 把 label_part 中的 | 替换为逗号
                # 但要保留首尾的 |
                if label_part.startswith('|') and label_part.endswith('|'):
                    inner = label_part[1:-1]
                    inner = inner.replace('|', ', ')
                    label_part = f'|{inner}|'
                line = line[:arrow_pos + 3] + label_part + node_part
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # 6. 修复 subgraph 命名
    # 格式：subgraph ID["Label"] 或 subgraph ID
    # 只替换 ID 部分，保留 Label 部分
    lines = text.splitlines()
    cleaned_lines = []
    for line in lines:
        if line.strip().startswith("subgraph "):
            match = re.match(r'(\s*subgraph\s+)([^\["\s]+)(.*)', line)
            if match:
                prefix = match.group(1)
                id_part = match.group(2).strip()
                rest = match.group(3)  # 可能包含 ["Label"]
                # 只清理 ID 部分
                id_part = re.sub(r'[^\w\-]', '_', id_part)
                line = prefix + id_part + rest
        cleaned_lines.append(line)
    text = "\n".join(cleaned_lines)

    # 7. 清理多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def validate_mermaid(text: str) -> tuple[bool, str]:
    """启发式校验 Mermaid 语法。"""
    if not text:
        return False, "空图表"

    lines = text.splitlines()
    if not lines:
        return False, "空图表"

    first_line = lines[0].strip().lower()
    valid_starts = [
        "graph ", "flowchart ", "sequencediagram", "classdiagram",
        "erdiagram", "gantt", "pie", "statediagram", "journey",
        "gitgraph", "mindmap", "timeline", "requirementdiagram"
    ]
    if not any(first_line.startswith(s) for s in valid_starts):
        return False, f"不支持的图表类型开头: {lines[0][:50]}"

    # 检查方括号匹配（粗略）
    open_sq = text.count('[')
    close_sq = text.count(']')
    if open_sq != close_sq:
        return False, f"方括号不匹配: 开{open_sq} 闭{close_sq}"

    open_cu = text.count('{')
    close_cu = text.count('}')
    if open_cu != close_cu:
        return False, f"花括号不匹配: 开{open_cu} 闭{close_cu}"

    return True, ""
