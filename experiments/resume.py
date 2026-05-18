"""
断点续跑：只重新生成失败的页面
"""
import asyncio
import json
from pathlib import Path

from code_parser import scan_directory
from storyboard_engine import generate_page

REPO_PATH = Path(__file__).parent / "test_repo"
OUTPUT_DIR = Path(__file__).parent / "output"
RESULT_PATH = OUTPUT_DIR / "result.json"

async def main():
    print("=" * 60)
    print("断点续跑：补全生成失败的页面")
    print("=" * 60)
    
    # 读取已有结果
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    pages = result["pages"]
    
    # 重新扫描代码库获取 file_contents
    _, file_contents = scan_directory(str(REPO_PATH))
    
    # 找出失败的页面
    failed_pages = []
    for idx, page in enumerate(pages):
        if "生成失败" in page.get("narration_text", "") or "生成失败" in page.get("mermaid_diagram", ""):
            failed_pages.append(idx)
    
    if not failed_pages:
        print("\n所有页面均已成功生成，无需补全。")
        return
    
    print(f"\n发现 {len(failed_pages)} 个失败页面: {failed_pages}")
    
    total_pages = len(pages)
    for idx in failed_pages:
        page = pages[idx]
        print(f"\n[补全] 第 {idx + 1}/{total_pages} 页: {page['title']}...")
        
        # 前情提要
        previous_summary = ""
        if idx > 0:
            prev_text = pages[idx - 1].get("narration_text", "")
            previous_summary = prev_text[:150] + "..." if len(prev_text) > 150 else prev_text
        
        # 下一页预告
        next_title = pages[idx + 1]["title"] if idx + 1 < total_pages else ""
        
        try:
            page_content = await generate_page(
                course_title=result.get("title", ""),
                narrative_mode=result.get("narrative_mode", ""),
                page=page,
                total_pages=total_pages,
                previous_summary=previous_summary,
                next_title=next_title,
                file_contents=file_contents,
            )
            
            pages[idx]["mermaid_diagram"] = page_content.get("mermaid_diagram", "")
            pages[idx]["narration_text"] = page_content.get("narration_text", "")
            
            print(f"   [成功]")
            print(f"      讲解文本长度: {len(pages[idx]['narration_text'])} 字符")
            print(f"      Mermaid 图表行数: {len(pages[idx]['mermaid_diagram'].splitlines())} 行")
            
            # 每成功一页就保存一次，避免再次失败丢失进度
            RESULT_PATH.write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            
        except Exception as e:
            print(f"   [再次失败] {e}")
    
    # 重新生成 Markdown 报告
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
    
    print("\n" + "=" * 60)
    print("[完成] 断点续跑结束，结果已更新")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
