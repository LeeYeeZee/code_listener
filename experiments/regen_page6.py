"""
修复第 6 页空 narration + \#quot; 污染，并重新生成该页内容
"""
import asyncio
import json
from pathlib import Path

from code_parser import scan_directory, build_code_summary
from storyboard_engine import generate_page, fix_mermaid
from diagram_renderer import render_mermaid
from mermaid_sanitizer import sanitize_mermaid

RESULT_PATH = Path("output/result.json")
STORYBOARD_PATH = Path("output/storyboard.json")
REPO_PATH = Path("leveldb")

async def main():
    # 1. 读取 storyboard 和 result
    storyboard = json.loads(STORYBOARD_PATH.read_text(encoding="utf-8"))
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    pages = result["pages"]
    
    # 2. 先全局修复 \#quot; -> #quot;
    fix_count = 0
    for p in pages:
        m = p.get("mermaid_diagram", "")
        if "\\#quot;" in m:
            p["mermaid_diagram"] = m.replace("\\#quot;", "#quot;")
            fix_count += 1
    print(f"全局修复 \\#quot; -> #quot;: {fix_count} 页")
    
    # 3. 重新生成第 6 页 (page_index=6)
    idx = 6
    page = storyboard["pages"][idx]
    total_pages = len(storyboard["pages"])
    
    # 准备代码上下文
    file_tree, file_contents = scan_directory(str(REPO_PATH))
    
    # previous_summary / next_title
    prev_summary = ""
    if idx > 0:
        prev = storyboard["pages"][idx - 1]
        prev_summary = f"上一页主题「{prev.get('focus', '')}」：{prev.get('cognitive_goal', '')}"
    next_title = storyboard["pages"][idx + 1]["title"] if idx + 1 < total_pages else ""
    
    print(f"\n重新生成第 {idx + 1} 页: {page['title']}...")
    try:
        page_content = await generate_page(
            course_title=storyboard.get("title", ""),
            narrative_mode=storyboard.get("narrative_mode", ""),
            page=page,
            total_pages=total_pages,
            previous_summary=prev_summary,
            next_title=next_title,
            file_contents=file_contents,
        )
    except Exception as e:
        print(f"  生成失败: {e}")
        return
    
    mermaid_text = page_content.get("mermaid_diagram", "")
    narration_text = page_content.get("narration_text", "")
    
    # sanitize
    mermaid_text = sanitize_mermaid(mermaid_text)
    
    # 渲染验证
    temp_png = Path("output/temp_mermaid/page_6_regen.png")
    render_result = await render_mermaid(mermaid_text, temp_png)
    
    if render_result:
        print(f"  渲染通过 ({len(mermaid_text.splitlines())} 行)")
    else:
        print(f"  渲染失败，尝试修复...")
        for retry in range(2):
            mermaid_text = await fix_mermaid(mermaid_text, "Mermaid语法解析错误")
            mermaid_text = sanitize_mermaid(mermaid_text)
            render_result = await render_mermaid(mermaid_text, temp_png)
            if render_result:
                print(f"  修复后渲染通过")
                break
        else:
            mermaid_text = "graph TD\n    A[图表渲染失败] --> B[请查看文本讲解]"
            print(f"  降级处理")
    
    # 更新 result
    pages[idx]["mermaid_diagram"] = mermaid_text
    pages[idx]["narration_text"] = narration_text
    
    print(f"  narration: {len(narration_text)} 字")
    
    # 保存
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已保存到 {RESULT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
