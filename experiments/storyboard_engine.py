"""
叙事引擎：两步生成流程 + Mermaid 渲染验证重试
增强版：严格 JSON 格式 + 高质量 Few-Shot Examples + 增强 Mermaid 规范
"""
import json
from typing import Dict, Any
from llm_client import chat_completion
import config

# ============================================================
# Few-Shot 示例（不参与 format，纯常量）
# ============================================================

STORYBOARD_FEW_SHOT_EXAMPLE = '''
{
  "title": "深入理解Redis事件循环",
  "narrative_mode": "layered",
  "total_pages": 3,
  "pages": [
    {
      "page_index": 0,
      "title": "Redis单线程架构全景",
      "focus": "事件循环整体机制",
      "cognitive_goal": "理解Redis为什么采用单线程，以及事件循环在整体架构中的位置",
      "scope_files": ["src/server.c", "src/ae.c"],
      "instruction": "画出aeEventLoop与网络IO、命令处理、持久化的关系，强调单线程+IO多路复用。必须包含：客户端连接、epoll_wait、命令执行、持久化子进程。",
      "depends_on": []
    },
    {
      "page_index": 1,
      "title": "aeEventLoop核心数据结构",
      "focus": "事件注册与文件描述符管理",
      "cognitive_goal": "理解aeEventLoop结构体的字段构成和事件注册机制",
      "scope_files": ["src/ae.h", "src/ae.c"],
      "instruction": "画出aeEventLoop结构体内部组成：events数组、maxfd、beforesleep/aftersleep回调。展示文件事件和时间事件的区别。",
      "depends_on": [0]
    },
    {
      "page_index": 2,
      "title": "事件分发与命令执行",
      "focus": "aeProcessEvents主循环执行流程",
      "cognitive_goal": "理解事件如何从epoll_wait分发到对应的处理器",
      "scope_files": ["src/ae.c", "src/networking.c"],
      "instruction": "画出aeProcessEvents的完整执行流程：epoll_wait -> 遍历就绪事件 -> 文件事件处理器(readQueryFromClient) -> 命令执行 -> 时间事件检查。",
      "depends_on": [1]
    }
  ]
}
'''

STORYBOARD_BAD_EXAMPLE = '''
❌ 不合格示例（切勿模仿）：
{
  "title": "Redis源码解析",         // 标题过于笼统，没有聚焦具体主题
  "narrative_mode": "layered",
  "total_pages": 1,                 // 错误：3个核心概念压缩到1页，讲不清楚
  "pages": [
    {
      "page_index": 0,
      "title": "Redis所有内容",      // 错误：标题覆盖面过大
      "focus": "",                  // 错误：focus为空，主题不明确
      "cognitive_goal": "学会Redis", // 错误：目标过于模糊
      "scope_files": [],            // 错误：没有精确到具体文件
      "instruction": "讲Redis",      // 错误：instruction过于模糊
      "depends_on": []
    }
  ]
}
'''

PAGE_FEW_SHOT_ARCHITECTURE = '''
【输入】
- 课程标题：微服务架构设计
- 叙事模式：layered
- 当前页：第1页 / 共4页
- 标题：四层微服务架构全景
- 聚焦：系统分层与组件关系
- 认知目标：理解微服务系统的四层划分和各层职责
- 代码上下文：[无特定代码上下文]

【输出】
{
  "mermaid_diagram": "graph TD\\n    subgraph client[\\"客户端层\\"]\\n        C1[\\"Web浏览器\\"]:::external\\n        C2[\\"移动端App\\"]:::external\\n    end\\n    \\n    subgraph gateway[\\"网关层\\"]\\n        G1[\\"Nginx反向代理\\"]:::external\\n        G2[\\"API Gateway\\"]:::core\\n    end\\n    \\n    subgraph service[\\"服务层\\"]\\n        S1[\\"用户服务\\"]:::core\\n        S2[\\"订单服务\\"]:::core\\n        S3[\\"支付服务\\"]:::core\\n    end\\n    \\n    subgraph data[\\"数据层\\"]\\n        D1[\\"MySQL主库\\"]:::data\\n        D2[\\"MySQL从库\\"]:::data\\n        D3[\\"Redis缓存\\"]:::data\\n        D4[\\"Kafka消息队列\\"]:::data\\n    end\\n    \\n    C1 --> G1\\n    C2 --> G1\\n    G1 --> G2\\n    G2 -->|\\"路由请求\\"| S1\\n    G2 -->|\\"路由请求\\"| S2\\n    G2 -->|\\"路由请求\\"| S3\\n    S1 -->|\\"读缓存\\"| D3\\n    S1 -->|\\"写数据\\"| D1\\n    D1 -.->|\\"主从同步\\"| D2\\n    S2 -->|\\"发送事件\\"| D4\\n    S3 -->|\\"消费事件\\"| D4\\n    \\n    classDef core fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333\\n    classDef data fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333\\n    classDef external fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#333",
  "narration_text": "好，我们先从整体架构入手。一个典型的微服务系统分为四层。最上面是客户端层，包括Web浏览器和移动端App，它们通过HTTPS发起请求。请求首先到达网关层的Nginx反向代理，Nginx做负载均衡后转发给API Gateway。API Gateway负责统一认证、限流和路由，把请求分发到下游的服务层。服务层包含用户服务、订单服务和支付服务三个核心微服务。每个服务只处理自己的领域逻辑，服务之间通过消息队列解耦。最后是数据层，MySQL主库负责写操作，从库通过主从同步承担读压力，Redis缓存加速热点数据访问，Kafka消息队列实现异步事件通知。这样的分层设计保证了系统的可扩展性和可维护性。下一页，我们深入到网关层，看看API Gateway内部是怎么工作的。"
}
'''

PAGE_FEW_SHOT_FLOW = '''
【输入】
- 课程标题：服务端请求处理
- 叙事模式：dataflow
- 当前页：第1页 / 共2页
- 标题：HTTP请求处理全链路
- 聚焦：请求从入口到响应的完整流程
- 认知目标：理解服务端处理HTTP请求的分支决策和错误处理
- 代码上下文：[无特定代码上下文]

【输出】
{
  "mermaid_diagram": "graph TD\\n    A[\\"客户端请求\\"]:::external --> B{\\"认证通过?\\"}:::decision\\n    B -->|\\"是\\"| C[\\"参数校验\\"]:::core\\n    B -->|\\"否\\"| D[\\"返回401\\"]:::error\\n    C -->|\\"通过\\"| E[\\"业务处理\\"]:::core\\n    C -->|\\"失败\\"| F[\\"返回400\\"]:::error\\n    E --> G{\\"操作类型?\\"}:::decision\\n    G -->|\\"读\\"| H[\\"查询缓存\\"]:::core\\n    G -->|\\"写\\"| I[\\"更新数据库\\"]:::data\\n    H -->|\\"命中\\"| J[\\"返回结果\\"]:::startEnd\\n    H -->|\\"未命中\\"| K[\\"查询数据库\\"]:::data\\n    K --> L[\\"写入缓存\\"]:::data\\n    L --> J\\n    I --> M[\\"发送消息\\"]:::data\\n    M --> J\\n    I -->|\\"失败\\"| N[\\"事务回滚\\"]:::error\\n    N --> O[\\"返回500\\"]:::error\\n    \\n    classDef core fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333\\n    classDef data fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333\\n    classDef external fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#333\\n    classDef decision fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#333\\n    classDef error fill:#FFEBEE,stroke:#E53935,stroke-width:2px,color:#333\\n    classDef startEnd fill:#F5F5F5,stroke:#757575,stroke-width:2px,color:#333",
  "narration_text": "接下来我们看看一个HTTP请求在服务端经历了哪些处理环节。首先，客户端请求进入系统，第一步是认证检查。如果认证不通过，直接返回401未授权错误。认证通过后，进入参数校验环节。参数不合法返回400错误。校验通过后，才进入核心业务处理。这里有一个分支判断：如果是读操作，优先查询Redis缓存。缓存命中直接返回结果，缓存未命中再去查数据库，查完回写缓存。如果是写操作，直接更新数据库，然后发送消息通知其他服务，最后返回结果。如果数据库更新失败，会触发事务回滚，返回500内部错误。整个流程有三个决策点和三条错误返回路径，这就是服务端请求处理的完整生命周期。"
}
'''

PAGE_FEW_SHOT_DATASTRUCT = '''
【输入】
- 课程标题：LevelDB核心数据结构
- 叙事模式：deepdive
- 当前页：第3页 / 共5页
- 标题：Slice：零拷贝的键值视图
- 聚焦：Slice如何避免不必要的内存拷贝
- 认知目标：理解Slice的设计思想和内存模型
- 代码上下文：leveldb::Slice 定义于 include/leveldb/slice.h，包含 data_ 指针和 size_ 长度

【输出】
{
  "mermaid_diagram": "graph TD\\n    subgraph memory_layout[\\"内存布局\\"]\\n        M1[\\"Raw Buffer<br>原始字节数组\\"]:::data\\n        M2[\\"Slice<br>offset + length\\"]:::core\\n        M3[\\"std::string_view<br>C++视图\\"]:::core\\n    end\\n    \\n    subgraph operations[\\"核心操作\\"]\\n        O1[\\"构造: Slice(data, offset, len)\\"]:::core\\n        O2[\\"比较: memcmp()\\"]:::core\\n        O3[\\"拷贝: memcpy()<br>深拷贝\\"]:::data\\n    end\\n    \\n    M1 -->|\\"引用\\"| M2\\n    M2 -->|\\"适配\\"| M3\\n    M2 -->|\\"调用\\"| O1\\n    M2 -->|\\"调用\\"| O2\\n    M2 -->|\\"避免\\"| O3\\n    \\n    classDef core fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333\\n    classDef data fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333",
  "narration_text": "现在我们来看LevelDB中一个非常精巧的设计：Slice。Slice是LevelDB用来避免不必要内存拷贝的核心数据结构。它的内存布局非常简单：底层是一个原始字节数组，Slice本身只保存两个字段，偏移量和长度。通过偏移和长度，Slice可以引用原始数组的任意一段数据，而不需要拷贝。从实现上看，Slice提供了和std::string_view类似的接口，支持构造、比较等操作。比较时直接调用memcmp，拷贝时也只用memcpy复制Slice结构本身，而不是复制底层数据。这个设计的核心思想是：能用引用就用引用，绝对不做深拷贝。这在大数据量场景下能节省大量内存和CPU时间。下一页我们来看看Slice在具体的键值操作中是怎么发挥作用的。"
}
'''

PAGE_BAD_MERMAID_EXAMPLES = '''
❌ 反例1：节点标签包含特殊字符但未用双引号包裹
   错误：A[BuildTable()] --> B[Header(7B)<br>数据部分]
   正确：A["BuildTable()"] --> B["Header(7B)<br>数据部分"]

❌ 反例2：连接线标签中有多对竖线
   错误：A -->|找到且非删除|se|type=Value| B
   正确：A -->|找到且非删除, type=Value| B

❌ 反例3：节点内部换行使用了 \\n 而非 <br>
   错误：A["第一行\\n第二行"]
   正确：A["第一行<br>第二行"]

❌ 反例4：subgraph ID 包含空格
   错误：subgraph build process
   正确：subgraph build_process["build process"]

❌ 反例5：节点 ID 使用中文
   错误：构建表 --> 生成文件
   正确：build_table --> generate_file

❌ 反例6：节点标签内部使用双引号，或错误地使用反斜杠+#quot;转义
   错误：A["hello \"world\""]、B["反斜杠+#quot;quoted反斜杠+#quot;"]
   正确：A['hello "world"']、B['quoted text']
'''

PAGE_BAD_NARRATION_EXAMPLES = '''
❌ 反例1：使用无意义的看图表述
   错误："从图中可以看到，系统分为几个部分..."
   问题：视频没有光标，观众看不到"图"，必须用语言描述清楚每个元素。

❌ 反例2：没有承接上文
   错误："Slice是LevelDB的数据结构..."（直接开始，没有上下文）
   正确："上一页我们了解了LevelDB的整体架构，现在深入到它的核心数据结构——Slice。"

❌ 反例3：偏离当前页主题
   错误：当前页标题是"WAL日志格式"，但 narration 讲了 MemTable 的实现。
   要求：narration_text 必须 100% 围绕当前页 title 和 focus 展开。

❌ 反例4：没有收尾句
   错误：讲解完当前页内容后戛然而止。
   正确：最后一句必须是总结当前页要点，或引出下一页内容的过渡句。
'''


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
    core_files_list = "\n".join(f"  - {f}" for f in core_files)
    
    messages = [
        {"role": "system", "content": TOPICS_SYSTEM_PROMPT},
        {"role": "user", "content": TOPICS_USER_PROMPT_TEMPLATE.format(
            code_summary=code_summary,
            core_files_list=core_files_list,
        )},
    ]
    
    # 主题枚举不需要完整代码，截断到 30000 字符即可
    truncated_summary = code_summary
    if len(truncated_summary) > 30000:
        truncated_summary = truncated_summary[:30000] + "\n... [truncated] ..."
    
    messages[1]["content"] = TOPICS_USER_PROMPT_TEMPLATE.format(
        code_summary=truncated_summary,
        core_files_list=core_files_list,
    )
    
    content = await chat_completion(
        messages=messages,
        temperature=0.3,
        response_format={"type": "json_object"},
        max_tokens=8000,
    )
    
    # LLM 可能返回 {"topics": [...]} 或直接返回 [...]
    data = json.loads(content)
    if isinstance(data, list):
        return data
    return data.get("topics", [])


# ============================================================
# 第1步：生成叙事大纲
# ============================================================

STORYBOARD_SYSTEM_PROMPT = f"""你是一位资深技术讲师和代码架构师，擅长将复杂代码讲解得清晰易懂。
你的任务是为一份代码仓库设计一份「幻灯片式」讲解大纲（Storyboard）。

核心原则：
- 每页 = 一张图 + 一段专门讲解该图的文本（严格1:1映射）
- 一个逻辑模块可以展开成多页，逐层深入
- 讲解必须有叙事连贯性，像一位老师在讲课
- 第1页必须是宏观概览，不能陷入细节
- 每页必须有明确的「认知目标」

输出格式严格约束（必须遵守）：
1. 输出必须是合法的 JSON 对象，**不要**包含 markdown 代码块标记（不要 ```json 或 ```）
2. 所有字符串字段**必须**使用双引号，禁止使用单引号
3. 所有必填字段**必须**存在且非空，禁止省略任何字段
4. "pages" 数组中的每个元素必须包含全部字段：page_index, title, focus, cognitive_goal, scope_files, instruction, depends_on
5. "depends_on" 必须是整数数组，没有依赖时写 []，禁止写 null
6. "scope_files" 必须是字符串数组，禁止写 null
7. "total_pages" 必须等于 "pages" 数组的实际长度

【合格示例】
{STORYBOARD_FEW_SHOT_EXAMPLE}

【不合格示例】
{STORYBOARD_BAD_EXAMPLE}

叙事模式选择（自动判断最适合的一种）：
1. 分层递进 (layered)：从架构全景 → 核心层 → 层内细节
2. 数据追踪 (dataflow)：跟随一个请求/数据的生命周期
3. 场景驱动 (scenario)：每个用户场景一页
4. 源码精读 (deepdive)：按代码阅读顺序讲解
"""

STORYBOARD_USER_PROMPT_TEMPLATE = """
以下是目标代码仓库的结构和关键代码内容：

{code_summary}

请根据代码库的模块复杂度和文件数量，为这份代码生成一份讲解 Storyboard。

**核心原则：以"能否讲清楚"为唯一划分标准**
- 每页只聚焦 **1 个核心概念**
- 判断标准：该概念能否在 1 页内讲清楚。如果不能，必须拆分为多页
- 宁可用 3 页讲透 1 个复杂主题，也不要用 1 页蜻蜓点水
- 页数由内容量和概念复杂度自主决定，不要人为压缩或合并

输出要求：
1. 输出严格的 JSON 格式（不要包含 markdown 代码块标记，只输出纯 JSON）
2. JSON 结构如下：
{{
  "title": "课程标题",
  "narrative_mode": "layered|dataflow|scenario|deepdive",
  "total_pages": 整数,
  "pages": [
    {{
      "page_index": 0,
      "title": "页面标题",
      "focus": "这页聚焦讲什么（15字以内）",
      "cognitive_goal": "学习者看完这页后应该理解什么",
      "scope_files": ["涉及的代码文件相对路径列表"],
      "instruction": "给后续生成该页内容时的具体指示",
      "depends_on": [依赖的页码索引]
    }}
  ]
}}

3. 每页的 scope_files 必须精确到实际存在的文件路径
4. 页与页之间用 depends_on 标明依赖，确保叙事连贯
5. 【极其重要】每页的 title、focus、cognitive_goal、instruction 四者必须严格指向同一主题
"""


async def generate_storyboard(code_summary: str, valid_files: set) -> Dict[str, Any]:
    """第1步：生成 Storyboard 大纲"""
    messages = [
        {"role": "system", "content": STORYBOARD_SYSTEM_PROMPT},
        {"role": "user", "content": STORYBOARD_USER_PROMPT_TEMPLATE.format(code_summary=code_summary)},
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


# ============================================================
# 第2步：逐页生成内容（Mermaid + 讲解文本）+ 渲染验证重试
# ============================================================

PAGE_SYSTEM_PROMPT = f"""你是一位技术讲师，正在为代码讲解课程的某一页准备幻灯片内容。

【输出格式】
每张幻灯片包含：
1. 一张 Mermaid 图表（可视化该页的核心概念）
2. 一段讲解文本（narration），口语化，适合朗读

你必须输出严格的 JSON 格式，禁止包含 markdown 代码块标记（不要 ```json 或 ```）。
JSON 必须包含两个字段：mermaid_diagram（字符串）和 narration_text（字符串）。

【图表布局要求：竖版短视频适配】
- 视频是竖版（9:16比例），图表必须适合竖版展示
- 优先使用 graph TD 或 flowchart TD（自上而下布局）
- 避免使用 graph LR（自左而右），否则图表会过于扁平
- 图表高度应大于宽度，节点之间留出足够的垂直间距
- 控制在 6-14 个节点以内，不要过度拥挤
- 节点文本要精简，使用 <br> 换行保持每行不超过8个汉字

【图表配色规范（必须遵守）】
为增强可读性和视觉吸引力，所有节点必须按语义角色着色。使用 classDef 定义颜色类，在节点后添加 :::className。

预定义语义类（按节点角色选用，不要自创类名）：
- core: 核心模块/主流程 → fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333
- data: 数据存储/数据库/文件 → fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333
- external: 外部服务/API/客户端 → fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#333
- decision: 判断条件/分支/检查 → fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#333
- error: 错误/异常/失败路径 → fill:#FFEBEE,stroke:#E53935,stroke-width:2px,color:#333
- startEnd: 开始/结束/入口/出口 → fill:#F5F5F5,stroke:#757575,stroke-width:2px,color:#333

着色示例（必须严格遵循此格式）：
  A["客户端请求"]:::external --> B{{"认证通过?"}}:::decision
  B -->|"是"| C["业务服务"]:::core
  B -->|"否"| D["返回401"]:::error
  C --> E["(数据库)"]:::data

  classDef core fill:#FFF3E0,stroke:#FB8C00,stroke-width:2px,color:#333
  classDef data fill:#E8F5E9,stroke:#43A047,stroke-width:2px,color:#333
  classDef external fill:#E3F2FD,stroke:#1E88E5,stroke-width:2px,color:#333
  classDef decision fill:#F3E5F5,stroke:#8E24AA,stroke-width:2px,color:#333
  classDef error fill:#FFEBEE,stroke:#E53935,stroke-width:2px,color:#333

【Mermaid 语法规范（必须严格遵守，违反会导致渲染失败）】
1. 节点标签包含括号、尖括号、方括号、花括号、引号等特殊字符时，必须用双引号包裹：
   正确：A["BuildTable()"]、B["Header(7B)<br>数据部分"]
   错误：A[BuildTable()]、B[Header(7B) + 数据]

2. 节点标签内部需要换行时，使用 <br>，绝对禁止用 \\n：
   正确：A["第一行<br>第二行"]
   错误：A["第一行\\n第二行"]

3. 连接线标签只能有一对 |...|，内部禁止出现额外的 |：
   正确：A -->|"找到且非删除, type=Value"| B
   错误：A -->|"找到且非删除|se|type=Value"| B

4. subgraph 命名只能包含字母、数字、下划线和横线，不能有空格：
   正确：subgraph build_process["构建过程"]
   错误：subgraph build process

5. 节点 ID 只能包含字母、数字和下划线，不能用中文或特殊符号：
   正确：A、B1、build_table
   错误：构建表、Build-Table!

6. 【极其重要】节点标签内部绝对禁止使用双引号 `"`，如有需要请用单引号 `'` 替代：
   正确：A['hello "world"']、B['BuildTable()']
   错误：A["hello \"world\""]、B["BuildTable()"]、C["反斜杠+#quot;quoted反斜杠+#quot;"]

7. 所有 classDef 声明必须放在图表末尾，放在节点定义之后

【讲解文本要求】
- 口语化，适合朗读，避免长句（每句不超过25个字）
- 开头用1句话承接上文或建立上下文
- 讲解必须严格对应图中的元素，做到"指哪打哪"
- 结尾用1句话总结当前页要点，或引出下一页内容
- 不要出现"如图所示""从图中可以看到"这类无意义表述（视频没有光标）
- 【极其重要】讲解文本必须严格围绕当前页的 title 和 focus 展开，绝对不能偏离主题
- 讲解时长由概念复杂度自主决定。简单概念30-45秒，复杂概念60-120秒。唯一约束：必须把当前页的聚焦内容讲清楚、讲透彻

【narration_text 三段式结构模板】
第1段（承接，1句话）："上一页我们了解了...，现在来看..." 或 "在深入细节之前，先建立整体认知..."
第2段（主体，按图中元素顺序逐层展开）：对每个关键节点/边进行解释，说明它的作用和与其他组件的关系。
第3段（收尾，1句话）："这就是...的核心机制，下一页我们将..." 或 "总结来说，..."

【高质量输出示例】
{PAGE_FEW_SHOT_ARCHITECTURE}

{PAGE_FEW_SHOT_FLOW}

{PAGE_FEW_SHOT_DATASTRUCT}

【常见错误（切勿犯）】
{PAGE_BAD_MERMAID_EXAMPLES}

{PAGE_BAD_NARRATION_EXAMPLES}
"""

PAGE_USER_PROMPT_TEMPLATE = """
课程信息：
- 课程标题：{course_title}
- 叙事模式：{narrative_mode}

当前页：第 {page_index} 页 / 共 {total_pages} 页
- 标题：{page_title}
- 聚焦：{focus}
- 认知目标：{cognitive_goal}
- 讲解时长由概念复杂度自主决定。简单概念30-45秒，复杂概念60-120秒。唯一约束：必须把当前页的聚焦内容讲清楚、讲透彻

前情提要：
{previous_summary}

下一页预告：
{next_title}

相关代码上下文：
{code_context}

请生成该页的严格 JSON 格式内容（不要包含 markdown 代码块标记）。
JSON 必须且只能包含以下两个字段：
{{
  "mermaid_diagram": "Mermaid 图表语法字符串，使用\\n换行。必须包含 classDef 语义着色。",
  "narration_text": "讲解文本，口语化，适合朗读。严格三段式：承接 + 逐元素讲解 + 收尾。"
}}
"""

MERMAID_FIX_PROMPT = """你之前生成的 Mermaid 图表有语法错误，导致无法渲染。

错误信息：
{error}

有问题的 Mermaid 代码：
{mermaid_code}

请修复上述语法错误，重新生成合法的 Mermaid 代码。注意：
1. 【极其重要】节点标签内部绝对禁止使用双引号 `"`，如有需要请用单引号 `'` 替代。这是最常见的错误来源。
2. 节点标签包含括号、尖括号、方括号、花括号、分号、管道符等特殊字符时，必须用外层双引号包裹整个标签，如 A["BuildTable()"]、B["Header(7B)<br>数据部分"]
3. 节点内部换行用 <br>，不要用 \\n
4. 连接线标签只能有一对 |...|
5. subgraph 命名不能有空格，用下划线替代
6. 节点 ID 只能是字母、数字和下划线，不能用中文
7. 保持图表适合竖版展示（graph TD，高度大于宽度）
8. 保留 classDef 语义着色

只输出修复后的 Mermaid 代码，不要输出其他内容。
"""


async def generate_page(
    course_title: str,
    narrative_mode: str,
    page: Dict[str, Any],
    total_pages: int,
    previous_summary: str,
    next_title: str,
    file_contents: Dict[str, str],
) -> Dict[str, str]:
    """第2步：为单页生成 Mermaid 图 + 讲解文本"""
    
    scope_files = page.get("scope_files", [])
    code_context_parts = []
    for f in scope_files:
        content = file_contents.get(f, "")
        if content:
            code_context_parts.append(f"--- {f} ---\n{content}")
    code_context = "\n\n".join(code_context_parts) if code_context_parts else "[无特定代码上下文]"
    
    if len(code_context) > 8000:
        code_context = code_context[:8000] + "\n... [truncated for context limit] ..."
    
    messages = [
        {"role": "system", "content": PAGE_SYSTEM_PROMPT},
        {"role": "user", "content": PAGE_USER_PROMPT_TEMPLATE.format(
            course_title=course_title,
            narrative_mode=narrative_mode,
            page_index=page["page_index"],
            total_pages=total_pages,
            page_title=page["title"],
            focus=page.get("focus", ""),
            cognitive_goal=page.get("cognitive_goal", ""),
            previous_summary=previous_summary or "（这是第一页，无前情提要）",
            next_title=next_title or "（这是最后一页，无下一页）",
            code_context=code_context,
        )},
    ]
    
    content = await chat_completion(
        messages=messages,
        temperature=0.4,
        response_format={"type": "json_object"},
    )
    
    page_content = json.loads(content)
    return page_content


async def fix_mermaid(mermaid_code: str, error: str) -> str:
    """Mermaid 渲染失败后，让 LLM 修复语法错误。"""
    messages = [
        {"role": "system", "content": "你是一位 Mermaid 语法专家，专门修复 LLM 生成的错误 Mermaid 代码。"},
        {"role": "user", "content": MERMAID_FIX_PROMPT.format(error=error, mermaid_code=mermaid_code)},
    ]
    
    fixed = await chat_completion(
        messages=messages,
        temperature=0.2,
    )
    
    # 清理可能的 markdown 代码块
    fixed = fixed.strip()
    if fixed.startswith("```"):
        lines = fixed.splitlines()
        # 去掉第一行和最后一行
        if len(lines) > 2:
            fixed = "\n".join(lines[1:-1])
        elif len(lines) == 2:
            fixed = lines[0].replace("```", "")
    
    return fixed.strip()
