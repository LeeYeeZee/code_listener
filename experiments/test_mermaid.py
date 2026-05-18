"""快速测试 Mermaid 渲染修复效果"""
import asyncio
import json
from pathlib import Path
from mermaid_sanitizer import sanitize_mermaid
from diagram_renderer import render_mermaid

async def main():
    result = json.loads(open('output/result.json', encoding='utf-8').read())
    output_dir = Path('output/videos')
    output_dir.mkdir(exist_ok=True)
    
    success = 0
    fail = 0
    
    for p in result['pages']:
        idx = p['page_index']
        title = p['title']
        raw = p['mermaid_diagram']
        clean = sanitize_mermaid(raw)
        png_path = output_dir / f'page_{idx:02d}.png'
        
        print(f'[page {idx}] {title}')
        if raw != clean:
            print('  [sanitized]')
        
        result_path = await render_mermaid(clean, png_path)
        if result_path:
            print(f'  [OK] {result_path}')
            success += 1
        else:
            print(f'  [FAIL]')
            fail += 1
        print()
    
    print(f"Summary: {success} success, {fail} fail")

if __name__ == "__main__":
    asyncio.run(main())
