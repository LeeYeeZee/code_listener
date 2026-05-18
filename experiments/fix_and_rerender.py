"""
批量修复 result.json 中的 Mermaid 语法错误并重新渲染
"""
import asyncio
import json
from pathlib import Path
from mermaid_sanitizer import sanitize_mermaid
from diagram_renderer import render_mermaid

RESULT_PATH = Path("output/result.json")
TEMP_DIR = Path("output/temp_mermaid")

async def main():
    result = json.loads(RESULT_PATH.read_text(encoding="utf-8"))
    pages = result.get("pages", [])
    
    print(f"共 {len(pages)} 页，开始批量修复...")
    
    fixed_count = 0
    fail_count = 0
    
    for p in pages:
        idx = p["page_index"]
        title = p["title"]
        mermaid = p.get("mermaid_diagram", "")
        
        # 1. 批量替换 \" -> #quot;
        if '\\"' in mermaid:
            mermaid = mermaid.replace('\\"', '#quot;')
            print(f"  [{idx}] {title}: 修复 \" -> #quot;")
        
        # 2. sanitize
        mermaid = sanitize_mermaid(mermaid)
        
        # 3. 重新渲染
        temp_png = TEMP_DIR / f"page_{idx}_fixed.png"
        render_result = await render_mermaid(mermaid, temp_png)
        
        if render_result:
            p["mermaid_diagram"] = mermaid
            fixed_count += 1
            print(f"  [{idx}] {title}: [OK] 渲染通过 ({len(mermaid.splitlines())} 行)")
        else:
            # 降级
            p["mermaid_diagram"] = "graph TD\n    A[图表渲染失败] --> B[请查看文本讲解]"
            fail_count += 1
            print(f"  [{idx}] {title}: [FAIL] 渲染失败，已降级")
    
    # 保存修复后的结果
    RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n修复完成: 通过 {fixed_count} / 降级 {fail_count} / 总计 {len(pages)}")
    print(f"已保存到: {RESULT_PATH}")

if __name__ == "__main__":
    asyncio.run(main())
