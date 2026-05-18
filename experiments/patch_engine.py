"""Patch storyboard_engine.py to add two-phase split functions"""
import re

NEW_CODE_BEFORE_STEP1 = '''
# ============================================================
# 阶段零：主题枚举（两阶段拆分 - 阶段一）
# ============================================================

TOPICS_SYSTEM_PROMPT = """你是一位技术文档架构师，擅长分析代码仓库并规划讲解结构。

你的任务是：遍历代码仓库中的所有核心文件，列出每一个需要单独讲解的技术主题。

拆分原则（必须遵守）：
1. 遍历所有核心代码文件（排除 test/util/format/config 等辅助文件），每个核心文件至少对应一个主题
2. 复杂主题（如 SSTable/Compaction/Iterator/Version）必须拆分为 2-3 个独立主题，不得合并
3. 宁拆勿并：宁可把一个主题拆成 3 页讲透，也不要用 1 页蜻蜓点水
4. 每个主题只聚焦 1 个核心概念，能在 1 页内讲清楚
5. 主题之间要有逻辑顺序，像一位老师在备课

输出格式严格约束：
- 输出 JSON 数组，不要 markdown 代码块
- 每个元素包含：topic_id, title, focus, scope_files, rationale
"""

TOPICS_USER_PROMPT_TEMPLATE = """
以下是目标代码仓库的摘要和文件列表：

{code_summary}

核心文件列表（已排除 test/util/format 等辅助文件）：
{core_files_list}

请基于上述代码，列出所有需要讲解的技术主题。

要求：
1. 每个核心文件至少对应一个主题
2. 复杂主题拆分为多个子主题
3. 按逻辑顺序排列
4. 输出严格 JSON 数组格式
"""


async def generate_topics(code_summary: str, core_files: list[str]) -> list[dict]:
    """阶段一：基于代码文件树枚举所有技术主题"""
    core_files_list = "\\n".join(f"  - {f}" for f in core_files)
    
    messages = [
        {"role": "system", "content": TOPICS_SYSTEM_PROMPT},
        {"role": "user", "content": TOPICS_USER_PROMPT_TEMPLATE.format(
            code_summary=code_summary,
            core_files_list=core_files_list,
        )},
    ]
    
    content = await chat_completion(
        messages=messages,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    
    # LLM 可能返回 {"topics": [...]} 或直接返回 [...]
    data = json.loads(content)
    if isinstance(data, list):
        return data
    return data.get("topics", [])


'''

NEW_CODE_AFTER_GENERATE_STORYBOARD = '''

async def generate_storyboard_from_topics(topics: list[dict], code_summary: str, valid_files: set) -> Dict[str, Any]:
    """阶段二：基于主题列表生成完整 Storyboard 大纲"""
    
    STORYBOARD_FROM_TOPICS_SYSTEM_PROMPT = """你是一位资深技术讲师和代码架构师。

基于已确定的主题列表，生成一份完整的 Storyboard 讲解大纲。

核心原则：
- 每页 = 一张图 + 一段专门讲解该图的文本（严格1:1映射）
- 第1页必须是宏观概览，不能陷入细节
- 每页必须有明确的「认知目标」
- 讲解必须有叙事连贯性，像一位老师在讲课

输出格式严格约束：
1. 输出必须是合法的 JSON 对象
2. 所有字符串字段必须使用双引号
3. 必填字段必须存在且非空
4. "depends_on" 必须是整数数组，无依赖时写 []
"""

    STORYBOARD_FROM_TOPICS_USER_PROMPT_TEMPLATE = """
已确定的主题列表（共 {total_topics} 个）：

{topics_json}

相关代码上下文：
{code_summary}

请基于上述主题列表，生成一份完整的 Storyboard 大纲。

输出要求：
1. 输出严格的 JSON 格式（不要 markdown 代码块）
2. JSON 结构：
{{
  "title": "课程标题",
  "narrative_mode": "layered|dataflow|scenario|deepdive",
  "total_pages": 整数,
  "pages": [
    {{
      "page_index": 0,
      "title": "页面标题",
      "focus": "聚焦点（15字以内）",
      "cognitive_goal": "学习者看完这页后应该理解什么",
      "scope_files": ["涉及的代码文件"],
      "instruction": "给后续生成该页内容时的具体指示",
      "depends_on": [依赖的页码索引]
    }}
  ]
}}

3. 每页的 scope_files 必须精确到实际存在的文件路径
4. 页与页之间用 depends_on 标明依赖，确保叙事连贯
5. 每页的 title、focus、cognitive_goal、instruction 四者必须严格指向同一主题
"""

    messages = [
        {"role": "system", "content": STORYBOARD_FROM_TOPICS_SYSTEM_PROMPT},
        {"role": "user", "content": STORYBOARD_FROM_TOPICS_USER_PROMPT_TEMPLATE.format(
            total_topics=len(topics),
            topics_json=json.dumps(topics, ensure_ascii=False, indent=2),
            code_summary=code_summary[:5000],
        )},
    ]
    
    content = await chat_completion(
        messages=messages,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    
    storyboard = json.loads(content)
    
    # 校验并清理 scope_files
    for page in storyboard.get("pages", []):
        cleaned = []
        for f in page.get("scope_files", []):
            f = f.strip()
            if f in valid_files and "_test." not in f and "_tests." not in f:
                cleaned.append(f)
        page["scope_files"] = cleaned
    
    return storyboard

'''

# Read original file
with open('storyboard_engine.py', encoding='utf-8') as f:
    original = f.read()

# Insert before Step 1
marker1 = '# ============================================================\n# 第1步：生成叙事大纲\n# ============================================================'
if marker1 not in original:
    print("ERROR: marker1 not found")
    exit(1)

patched = original.replace(marker1, NEW_CODE_BEFORE_STEP1 + marker1)

# Insert after generate_storyboard function
marker2 = '\n# ============================================================\n# 第2步：逐页生成内容'
if marker2 not in original:
    print("ERROR: marker2 not found")
    exit(1)

patched = patched.replace(marker2, NEW_CODE_AFTER_GENERATE_STORYBOARD + marker2)

# Write back
with open('storyboard_engine.py', 'w', encoding='utf-8') as f:
    f.write(patched)

print("Patch applied successfully")
