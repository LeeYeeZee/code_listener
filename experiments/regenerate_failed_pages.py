"""
重新生成渲染失败的页面
"""
import asyncio
import json
import sys
from pathlib import Path

from code_parser import scan_directory, build_code_summary
from storyboard_engine import generate_page, fix_mermaid
from diagram_renderer import render_mermaid
from mermaid_sanitizer import sanitize_mermaid

OUTPUT_DIR = Path(__file__).parent / "output"
LLM_SEMAPHORE = asyncio.Semaphore(5)


async def regenerate_page(idx: int, storyboard: dict, file_contents: dict) -> dict:
    """重新生成单个失败页面"""
    pages = storyboard["pages"]
    page = pages[idx]
    total_pages = len(pages)
    page_title = page.get("title", f"page_{idx}")
    print(f"[重新生成] 第 {idx + 1}/{total_pages} 页: {page_title}")

    # 前情提要
    previous_summary = ""
    if idx > 0:
        prev = pages[idx - 1]
        prev_focus = prev.get("focus", "")
        prev_goal = prev.get("cognitive_goal", "")
        previous_summary = f"上一页主题「{prev_focus}」：{prev_goal}"

    next_title = ""
    if idx + 1 < total_pages:
        next_title = pages[idx + 1]["title"]

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
        except Exception as e:
            print(f"  [警告] 生成失败: {e}")
            return None

    mermaid_text = page_content.get("mermaid_diagram", "")
    narration_text = page_content.get("narration_text", "")

    # Sanitize
    mermaid_text = sanitize_mermaid(mermaid_text)

    # 渲染验证 + LLM 修复重试
    temp_dir = OUTPUT_DIR / "temp_mermaid"
    temp_dir.mkdir(exist_ok=True)
    max_render_retries = 2
    render_ok = False
    for retry in range(max_render_retries + 1):
        temp_png = temp_dir / f"page_{idx}_regen_retry_{retry}.png"
        render_result = await render_mermaid(mermaid_text, temp_png)
        if render_result:
            render_ok = True
            break
        else:
            if retry < max_render_retries:
                async with LLM_SEMAPHORE:
                    print(f"  [渲染失败，LLM修复，重试 {retry + 1}/{max_render_retries}]...")
                    error_hint = "Mermaid语法解析错误，请检查节点标签的引号包裹、换行符、连接线标签格式等"
                    mermaid_text = await fix_mermaid(mermaid_text, error_hint)
                    mermaid_text = sanitize_mermaid(mermaid_text)
            else:
                print(f"  [渲染失败，已达最大重试次数，使用降级图表]")
                mermaid_text = "graph TD\n    A[图表渲染失败] --> B[请查看文本讲解]"

    result = {
        **page,
        "mermaid_diagram": mermaid_text,
        "narration_text": narration_text,
    }
    print(f"  [完成] 第 {idx + 1} 页 | 文本 {len(narration_text)} 字 | 图表 {len(mermaid_text.splitlines())} 行 | 渲染{'通过' if render_ok else '降级'}")
    return result


async def main():
    repo_path = Path(__file__).parent / "leveldb"
    if not repo_path.exists():
        print(f"[错误] leveldb 不存在")
        sys.exit(1)

    # 扫描代码
    print("[扫描代码]...")
    file_tree, file_contents = scan_directory(str(repo_path))
    code_summary = build_code_summary(file_tree, file_contents)
    valid_files = set(file_tree)

    # 加载 storyboard
    storyboard_path = OUTPUT_DIR / "storyboard.json"
    storyboard = json.loads(storyboard_path.read_text(encoding="utf-8"))

    # 加载当前 result.json
    result_path = OUTPUT_DIR / "result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    pages = result["pages"]

    # 找出渲染失败的页面
    failed_indices = []
    for idx, p in enumerate(pages):
        m = p.get("mermaid_diagram", "")
        if "图表渲染失败" in m or "处理异常" in m or "生成失败" in m or len(m.splitlines()) < 3:
            failed_indices.append(idx)

    print(f"\n发现 {len(failed_indices)} 个失败页面: {[i + 1 for i in failed_indices]}")

    if not failed_indices:
        print("没有失败页面，无需重新生成")
        return

    # 重新生成失败的页面
    tasks = [regenerate_page(idx, storyboard, file_contents) for idx in failed_indices]
    new_pages_results = await asyncio.gather(*tasks)

    # 更新 result
    for idx, new_page in zip(failed_indices, new_pages_results):
        if new_page:
            pages[idx] = new_page

    # 保存更新后的 result
    result["pages"] = pages
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已更新: {result_path}")

    # 更新 report.md
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
    print(f"已更新: {OUTPUT_DIR / 'report.md'}")

    # 统计最终结果
    ok = sum(1 for p in pages if "图表渲染失败" not in p.get("mermaid_diagram", ""))
    print(f"\n最终统计: {ok}/{len(pages)} 页渲染通过")


if __name__ == "__main__":
    asyncio.run(main())
