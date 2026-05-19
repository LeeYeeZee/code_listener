"""
视频合成管道：读取 result.json，逐页生成视频（Mermaid→PNG→TTS→FFmpeg）

用法：
    python video_pipeline.py [result.json路径] [--repo test_repo|leveldb]

默认读取 experiments/output/result.json
"""
import asyncio
import json
import sys
from pathlib import Path

from diagram_renderer import render_mermaid
from tts_service import synthesize_speech, synthesize_speech_mimo
from video_maker import make_video, make_title_video, concat_videos
from title_card import generate_title_card
from mermaid_sanitizer import sanitize_mermaid, validate_mermaid
import config

OUTPUT_DIR = Path(__file__).parent / "output"
VIDEO_DIR = OUTPUT_DIR / "videos"

async def main():
    # 解析命令行参数
    result_path = Path(__file__).parent / "output" / "result.json"
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        result_path = Path(sys.argv[1])
    
    if not result_path.exists():
        print(f"[错误] 找不到结果文件: {result_path}")
        print("   请先运行: python main.py")
        sys.exit(1)
    
    print("=" * 60)
    print("视频合成管道")
    print(f"输入: {result_path}")
    print("=" * 60)
    
    result = json.loads(result_path.read_text(encoding="utf-8"))
    pages = result.get("pages", [])
    
    VIDEO_DIR.mkdir(exist_ok=True)
    
    success_count = 0
    fail_count = 0
    
    for idx, page in enumerate(pages):
        page_title = page.get("title", f"page_{idx}")
        page_focus = page.get("focus", "")
        # 使用英文文件名避免编码问题
        safe_title = f"page_{idx:02d}"
        
        print(f"\n[第 {idx + 1}/{len(pages)} 页] {page_title}")
        
        mermaid_text = page.get("mermaid_diagram", "")
        narration_text = page.get("narration_text", "")
        
        if not mermaid_text or not narration_text:
            print(f"   [跳过] 内容为空")
            fail_count += 1
            continue
        
        # 清理 Mermaid 语法
        mermaid_text = sanitize_mermaid(mermaid_text)
        is_valid, err_msg = validate_mermaid(mermaid_text)
        if not is_valid:
            print(f"   [警告] Mermaid 语法检查未通过: {err_msg}")
        
        # 定义输出路径（使用英文避免编码问题）
        png_path = VIDEO_DIR / f"{safe_title}.png"
        mp3_path = VIDEO_DIR / f"{safe_title}.mp3"
        content_mp4_path = VIDEO_DIR / f"{safe_title}_content.mp4"
        final_mp4_path = VIDEO_DIR / f"{safe_title}.mp4"
        title_png_path = VIDEO_DIR / f"{safe_title}_title.png"
        title_mp4_path = VIDEO_DIR / f"{safe_title}_title.mp4"
        
        # Step 1: 渲染 Mermaid 图表
        print(f"   [Step 1/4] 渲染 Mermaid 图表...")
        png = await render_mermaid(mermaid_text, png_path)
        if not png:
            print(f"   [跳过] 图表渲染失败")
            fail_count += 1
            continue
        
        # Step 2: TTS 合成音频
        print(f"   [Step 2/4] TTS 合成音频...")
        
        # 智能选择 TTS 引擎：优先 MiniMax，未配置则 fallback 到 MiMo
        if config.MINIMAX_API_KEY:
            mp3 = await synthesize_speech(narration_text, mp3_path)
        elif config.MIMO_API_KEY:
            print(f"      [提示] MiniMax 未配置，使用 MiMo TTS")
            mp3 = await synthesize_speech_mimo(narration_text, mp3_path)
        else:
            print(f"   [跳过] 未配置任何 TTS API（MiniMax 或 MiMo）")
            fail_count += 1
            continue
        
        if not mp3:
            print(f"   [跳过] 音频合成失败")
            fail_count += 1
            continue
        
        # Step 3: FFmpeg 合成内容视频
        print(f"   [Step 3/4] FFmpeg 合成内容视频...")
        content_mp4 = await make_video(png, mp3, content_mp4_path)
        if not content_mp4:
            print(f"   [跳过] 内容视频合成失败")
            fail_count += 1
            continue
        
        # Step 4: 生成标题卡片 + 拼接
        print(f"   [Step 4/4] 生成标题卡片并拼接...")
        generate_title_card(
            title=page_title,
            description=page_focus,
            page_index=idx,
            total_pages=len(pages),
            output_path=title_png_path,
        )
        title_mp4 = await make_title_video(title_png_path, title_mp4_path, duration=2)
        if not title_mp4:
            print(f"   [跳过] 标题视频合成失败")
            fail_count += 1
            continue
        
        final_mp4 = await concat_videos([title_mp4, content_mp4], final_mp4_path)
        if not final_mp4:
            print(f"   [跳过] 视频拼接失败")
            fail_count += 1
            continue
        
        # 清理中间文件
        content_mp4_path.unlink(missing_ok=True)
        title_mp4_path.unlink(missing_ok=True)
        
        print(f"   [完成] 视频: {final_mp4_path.name}")
        success_count += 1
    
    print("\n" + "=" * 60)
    print(f"合成完成: 成功 {success_count} / 失败 {fail_count} / 总计 {len(pages)}")
    print(f"输出目录: {VIDEO_DIR}")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())
