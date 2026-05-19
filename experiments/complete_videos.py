"""
完成全部 35 页视频生成
- 第 0-13 页：已有 MiniMax MP3，重新生成标题卡 + MP4
- 第 14-24 页：已有 PNG，MiMo TTS + 标题卡 + MP4
- 第 25-34 页：重新渲染 Mermaid + MiMo TTS + 标题卡 + MP4
"""
import asyncio
import json
import sys
from pathlib import Path

from diagram_renderer import render_mermaid
from tts_service import synthesize_speech_mimo
from video_maker import make_video, make_title_video, concat_videos
from title_card import generate_title_card
from mermaid_sanitizer import sanitize_mermaid, validate_mermaid
import config

OUTPUT_DIR = Path(__file__).parent / "output"
VIDEO_DIR = OUTPUT_DIR / "videos"


async def process_page(idx: int, page: dict, total_pages: int, course_title: str) -> bool:
    """处理单页，返回是否成功"""
    page_title = page.get("title", f"page_{idx}")
    page_focus = page.get("focus", "")
    safe_title = f"page_{idx:02d}"
    
    print(f"\n[第 {idx + 1}/{total_pages} 页] {page_title}")
    
    mermaid_text = page.get("mermaid_diagram", "")
    narration_text = page.get("narration_text", "")
    
    if not mermaid_text or not narration_text:
        print(f"   [跳过] 内容为空")
        return False
    
    mermaid_text = sanitize_mermaid(mermaid_text)
    
    # 定义输出路径
    png_path = VIDEO_DIR / f"{safe_title}.png"
    mp3_path = VIDEO_DIR / f"{safe_title}.mp3"
    content_mp4_path = VIDEO_DIR / f"{safe_title}_content.mp4"
    final_mp4_path = VIDEO_DIR / f"{safe_title}.mp4"
    title_png_path = VIDEO_DIR / f"{safe_title}_title.png"
    title_mp4_path = VIDEO_DIR / f"{safe_title}_title.mp4"
    
    # Step 1: 确保有 PNG（图表）
    if png_path.exists() and png_path.stat().st_size > 1000:
        print(f"   [Step 1/4] 图表已存在，跳过渲染")
        png = png_path
    else:
        print(f"   [Step 1/4] 渲染 Mermaid 图表...")
        png = await render_mermaid(mermaid_text, png_path)
        if not png:
            print(f"   [失败] 图表渲染失败")
            return False
    
    # Step 2: 确保有 MP3（音频）
    if mp3_path.exists() and mp3_path.stat().st_size > 1000:
        print(f"   [Step 2/4] 音频已存在，跳过 TTS")
        audio = mp3_path
    else:
        print(f"   [Step 2/4] MiMo TTS 合成音频...")
        audio = await synthesize_speech_mimo(narration_text, mp3_path)
        if not audio:
            print(f"   [失败] MiMo TTS 合成失败")
            return False
    
    # Step 3: FFmpeg 合成内容视频
    print(f"   [Step 3/4] FFmpeg 合成内容视频...")
    content_mp4 = await make_video(png, audio, content_mp4_path)
    if not content_mp4:
        print(f"   [失败] 内容视频合成失败")
        return False
    
    # Step 4: 生成标题卡片 + 拼接
    print(f"   [Step 4/4] 生成标题卡片并拼接...")
    generate_title_card(
        title=page_title,
        description=page_focus,
        page_index=idx,
        total_pages=total_pages,
        output_path=title_png_path,
        course_title=course_title,
    )
    title_mp4 = await make_title_video(title_png_path, title_mp4_path, duration=2)
    if not title_mp4:
        print(f"   [失败] 标题视频合成失败")
        return False
    
    final_mp4 = await concat_videos([title_mp4, content_mp4], final_mp4_path)
    if not final_mp4:
        print(f"   [失败] 视频拼接失败")
        return False
    
    # 清理中间文件
    content_mp4_path.unlink(missing_ok=True)
    title_mp4_path.unlink(missing_ok=True)
    
    final_size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"   [完成] 视频: {final_mp4_path.name} ({final_size_mb:.1f} MB)")
    return True


async def main():
    result_path = OUTPUT_DIR / "result.json"
    if not result_path.exists():
        print("[错误] 找不到 result.json")
        sys.exit(1)
    
    result = json.loads(result_path.read_text(encoding="utf-8"))
    pages = result.get("pages", [])
    total_pages = len(pages)
    course_title = result.get("title", "")
    
    print("=" * 60)
    print("完成全部视频生成")
    print(f"课程: {course_title}")
    print(f"总页数: {total_pages}")
    print(f"策略: 已有MP3的跳过TTS，其余用MiMo")
    print("=" * 60)
    
    VIDEO_DIR.mkdir(exist_ok=True)
    
    success_count = 0
    fail_count = 0
    skipped_tts = 0
    
    for idx, page in enumerate(pages):
        mp3_path = VIDEO_DIR / f"page_{idx:02d}.mp3"
        if mp3_path.exists() and mp3_path.stat().st_size > 1000:
            skipped_tts += 1
        
        ok = await process_page(idx, page, total_pages, course_title)
        if ok:
            success_count += 1
        else:
            fail_count += 1
    
    print("\n" + "=" * 60)
    print(f"合成完成: 成功 {success_count} / 失败 {fail_count} / 总计 {total_pages}")
    print(f"跳过TTS: {skipped_tts} 页（使用已有MiniMax音频）")
    print(f"输出目录: {VIDEO_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
