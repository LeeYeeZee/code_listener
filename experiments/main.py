"""
叙事切分引擎验证脚本（并发优化版）

用法：
1. 复制 .env.example 为 .env，填入你的 LLM API Key
2. python main.py

流程：
  扫描 test_repo/ → 生成代码摘要 → LLM生成Storyboard大纲 → 【并发】逐页生成Mermaid+文本+渲染验证 → 输出结果
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from code_parser import scan_directory, build_code_summary
from storyboard_engine import (
    generate_storyboard, generate_page, fix_mermaid,
    generate_topics, generate_storyboard_from_topics,
)
from diagram_renderer import render_mermaid
from mermaid_sanitizer import sanitize_mermaid

# 输出目录
OUTPUT_DIR = Path(__file__).parent / "output"

# LLM 并发控制：同时最多 5 个页面在生成/修复中
LLM_SEMAPHORE = asyncio.Semaphore(5)


async def process_single_page(
    idx: int,
    page: dict,
    total_pages: int,
    storyboard: dict,
    file_contents: dict,
    temp_dir: Path,
) -> dict:
    """
    处理单个页面：生成内容 → sanitize → 渲染验证 → 返回完整页面数据。
    内部用 semaphore 控制 LLM 调用并发度。
    """
    page_title = page.get("title", f"page_{idx}")
    print(f"   [启动] 第 {idx + 1}/{total_pages} 页: {page_title}")

    async with LLM_SEMAPHORE:
        # 前情提要：用前一页的 focus + cognitive_goal 替代 narration 截断
        # 这样不需要等前一页生成完毕，支持完全并发
        previous_summary = ""
        if idx > 0:
            prev = storyboard["pages"][idx - 1]
            prev_focus = prev.get("focus", "")
            prev_goal = prev.get("cognitive_goal", "")
            previous_summary = f"上一页主题「{prev_focus}」：{prev_goal}"

        # 下一页预告
        next_title = ""
        if idx + 1 < total_pages:
            next_title = storyboard["pages"][idx + 1]["title"]

        # 1. LLM 生成内容
        try:
            page_content = await generate_page(
                course_title=storyboard.get("title", ""),
                narrative_mode=storyboard.get("narrative_mode", ""),
                page=page,
                total_pages=total_pages,
                previous_summary=previous_summary,
                next_title=next_title,
                file_contents=file_contents,
            )
        except Exception as e:
            print(f"   [警告] 第 {idx + 1} 页生成失败: {e}")
            page_content = {
                "mermaid_diagram": "graph TD\n    A[生成失败] --> B[请检查日志]",
                "narration_text": f"本页内容生成时出错: {e}",
            }

    mermaid_text = page_content.get("mermaid_diagram", "")
    narration_text = page_content.get("narration_text", "")

    # 2. 【质量检查】 narration 为空 或 mermaid 过简（少于5行）→ 自动重试生成
    is_bad_content = (
        not narration_text or not narration_text.strip()
        or not mermaid_text or len(mermaid_text.strip().splitlines()) < 5
    )
    if is_bad_content:
        print(f"   [警告] 第 {idx + 1} 页内容异常(narration空或mermaid过简)，自动重试生成...")
        async with LLM_SEMAPHORE:
            try:
                page_content = await generate_page(
                    course_title=storyboard.get("title", ""),
                    narrative_mode=storyboard.get("narrative_mode", ""),
                    page=page,
                    total_pages=total_pages,
                    previous_summary=previous_summary,
                    next_title=next_title,
                    file_contents=file_contents,
                )
                mermaid_text = page_content.get("mermaid_diagram", "")
                narration_text = page_content.get("narration_text", "")
                print(f"   [重试成功] 第 {idx + 1} 页重新生成完成")
            except Exception as e:
                print(f"   [重试失败] 第 {idx + 1} 页: {e}")

    # 3. Sanitize Mermaid（本地操作，无需 semaphore）
    mermaid_text = sanitize_mermaid(mermaid_text)

    # 4. 渲染验证 + LLM 修复重试
    max_render_retries = 2
    render_ok = False
    for retry in range(max_render_retries + 1):
        temp_png = temp_dir / f"page_{idx}_retry_{retry}.png"
        render_result = await render_mermaid(mermaid_text, temp_png)

        if render_result:
            render_ok = True
            break
        else:
            if retry < max_render_retries:
                async with LLM_SEMAPHORE:
                    print(f"      [第 {idx + 1} 页渲染失败，LLM修复，重试 {retry + 1}/{max_render_retries}]...")
                    error_hint = "Mermaid语法解析错误，请检查节点标签的引号包裹、换行符、连接线标签格式等"
                    mermaid_text = await fix_mermaid(mermaid_text, error_hint)
                    mermaid_text = sanitize_mermaid(mermaid_text)
            else:
                print(f"      [第 {idx + 1} 页渲染失败，已达最大重试次数，使用降级图表]")
                mermaid_text = "graph TD\n    A[图表渲染失败] --> B[请查看文本讲解]"

    # 5. 组装完整页面
    full_page = {
        **page,
        "mermaid_diagram": mermaid_text,
        "narration_text": narration_text,
    }

    print(f"   [完成] 第 {idx + 1}/{total_pages} 页: {page_title} | "
          f"文本 {len(narration_text)} 字 | 图表 {len(mermaid_text.splitlines())} 行 | "
          f"渲染{'通过' if render_ok else '降级'}")
    return full_page


async def main():
    import sys
    if len(sys.argv) > 1:
        repo_path = Path(sys.argv[1])
    else:
        repo_path = Path(__file__).parent / "test_repo"
    if not repo_path.exists():
        print(f"[错误] 测试代码库不存在: {repo_path}")
        sys.exit(1)

    print("=" * 60)
    print("CodeWiki 叙事切分引擎验证（并发版）")
    print(f"目标仓库: {repo_path}")
    print(f"LLM 并发度: {LLM_SEMAPHORE._value}")
    print("=" * 60)

    # Step 1: 代码预处理
    print("\n[Step 1] 扫描代码仓库...")
    file_tree, file_contents = scan_directory(str(repo_path))
    print(f"   发现 {len(file_tree)} 个文件")
    for p in file_tree:
        print(f"      * {p}")

    code_summary = build_code_summary(file_tree, file_contents)
    print(f"\n   代码摘要长度: {len(code_summary)} 字符")

    # 保存代码摘要供查看
    OUTPUT_DIR.mkdir(exist_ok=True)
    (OUTPUT_DIR / "code_summary.txt").write_text(code_summary, encoding="utf-8")
    print(f"   已保存到: {OUTPUT_DIR / 'code_summary.txt'}")

    # Step 2: 两阶段拆分 - 阶段一：主题枚举
    print("\n[Step 2] 两阶段拆分 - 阶段一：主题枚举...")
    
    # 过滤核心文件（排除 test/util/format/config 等辅助文件）
    def _is_core_file(f: str) -> bool:
        if "_test." in f or "_tests." in f:
            return False
        if f.startswith("."):
            return False
        # 排除纯工具类文件（保留 cache/bloom/arena 等基础设施）
        pure_utils = ["util/histogram.cc", "util/histogram.h", "util/testutil.cc",
                      "util/testutil.h", "util/logging.cc", "util/logging.h",
                      "util/posix_logger.h", "util/windows_logger.h",
                      "util/env_posix_test_helper.h", "util/env_windows_test_helper.h",
                      "util/no_destructor.h", "util/random.h", "util/mutexlock.h"]
        if f in pure_utils:
            return False
        return True
    
    core_files = [f for f in file_tree if _is_core_file(f)]
    print(f"   核心文件: {len(core_files)} / {len(file_tree)}")
    
    topics_path = OUTPUT_DIR / "topics.json"
    
    if not topics_path.exists():
        print("   topics.json 不存在，执行阶段一：主题枚举...")
        try:
            topics = await generate_topics(code_summary, core_files)
        except RuntimeError as e:
            print(f"\n   [错误] {e}")
            sys.exit(1)
        
        # 保存主题列表
        topics_path.write_text(
            json.dumps(topics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n   [成功] 主题枚举完成！共 {len(topics)} 个主题")
        print(f"   已保存到: {topics_path}")
        print("\n" + "=" * 60)
        print("【审阅提示】请检查 topics.json，可手动增删主题后重新运行")
        print("=" * 60)
        return  # 退出，等待用户审阅
    
    # 读取已审阅的主题列表
    topics = json.loads(topics_path.read_text(encoding="utf-8"))
    print(f"   已加载审阅后的主题列表: {len(topics)} 个主题")
    for t in topics:
        print(f"      [{t.get('topic_id', '?')}] {t.get('title', '')} ({t.get('focus', '')})")
    
    # Step 3: 两阶段拆分 - 阶段二：基于主题列表生成 Storyboard
    print("\n[Step 3] 两阶段拆分 - 阶段二：基于主题列表生成 Storyboard...")
    valid_files = set(file_tree)
    try:
        storyboard = await generate_storyboard_from_topics(topics, code_summary, valid_files)
    except RuntimeError as e:
        print(f"\n   [错误] {e}")
        sys.exit(1)
    
    print(f"\n   [成功] Storyboard 生成成功！")
    print(f"   课程标题: {storyboard.get('title', 'N/A')}")
    print(f"   叙事模式: {storyboard.get('narrative_mode', 'N/A')}")
    print(f"   总页数: {storyboard.get('total_pages', 0)}")
    
    # 保存大纲
    (OUTPUT_DIR / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"   已保存到: {OUTPUT_DIR / 'storyboard.json'}")
    
    # 打印大纲概览
    print("\n   [大纲概览]:")
    for page in storyboard.get("pages", []):
        deps = page.get("depends_on", [])
        deps_str = f" <- 依赖页{deps}" if deps else ""
        print(f"      [{page['page_index']}] {page['title']} ({page.get('focus', '')}){deps_str}")
    
    # Step 4: 【并发】逐页生成内容 + Mermaid 渲染验证
    print("\n[Step 4] 并发生成 Mermaid 图 + 讲解文本（含渲染验证）...")
    pages = storyboard.get("pages", [])
    total_pages = len(pages)

    # 临时目录用于渲染验证
    temp_dir = OUTPUT_DIR / "temp_mermaid"
    temp_dir.mkdir(exist_ok=True)

    # 构建所有并发任务
    tasks = [
        process_single_page(
            idx=idx,
            page=page,
            total_pages=total_pages,
            storyboard=storyboard,
            file_contents=file_contents,
            temp_dir=temp_dir,
        )
        for idx, page in enumerate(pages)
    ]

    # 并发执行，gather 返回结果列表（与 tasks 顺序一致）
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 收集结果，过滤异常
    generated_pages = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            print(f"   [错误] 第 {idx + 1} 页处理异常: {result}")
            # 构造降级页面
            fallback_page = {
                **pages[idx],
                "mermaid_diagram": "graph TD\n    A[处理异常] --> B[请检查日志]",
                "narration_text": f"本页处理时发生异常: {result}",
            }
            generated_pages.append(fallback_page)
        else:
            generated_pages.append(result)

    # 按 page_index 排序确保顺序正确
    generated_pages.sort(key=lambda p: p.get("page_index", 0))

    # Step 4: 保存最终输出
    print("\n[Step 5] 保存最终结果...")
    result = {
        "title": storyboard.get("title", ""),
        "narrative_mode": storyboard.get("narrative_mode", ""),
        "pages": generated_pages,
    }
    (OUTPUT_DIR / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"   已保存到: {OUTPUT_DIR / 'result.json'}")

    # 同时保存人类可读的 Markdown 报告
    md_lines = []
    md_lines.append(f"# {result['title']}\n")
    md_lines.append(f"**叙事模式**: {result['narrative_mode']}\n")
    md_lines.append(f"**总页数**: {len(result['pages'])}\n")
    md_lines.append("---\n")

    for p in result["pages"]:
        md_lines.append(f"\n## 第 {p['page_index'] + 1} 页: {p['title']}\n")
        md_lines.append(f"**聚焦**: {p.get('focus', '')}\n")
        md_lines.append(f"**认知目标**: {p.get('cognitive_goal', '')}\n")
        md_lines.append(f"**涉及文件**: {', '.join(p.get('scope_files', []))}\n")
        md_lines.append("\n### 图表\n")
        md_lines.append("```mermaid\n")
        md_lines.append(p.get("mermaid_diagram", ""))
        md_lines.append("\n```\n")
        md_lines.append("\n### 讲解文本\n")
        md_lines.append(p.get("narration_text", ""))
        md_lines.append("\n")

    (OUTPUT_DIR / "report.md").write_text("\n".join(md_lines), encoding="utf-8")
    print(f"   已保存到: {OUTPUT_DIR / 'report.md'}")

    print("\n" + "=" * 60)
    print("[完成] 验证完成！所有输出已保存到 experiments/output/ 目录")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
