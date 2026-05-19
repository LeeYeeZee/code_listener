"""
MiMo TTS + 视频合成 端到端测试（只处理第1页）
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

OUTPUT_DIR = Path(__file__).parent / "output"
VIDEO_DIR = OUTPUT_DIR / "videos_test"


async def main():
    result_path = OUTPUT_DIR / "result.json"
    if not result_path.exists():
        print("[错误] 找不到 result.json，请先运行 main.py")
        sys.exit(1)

    result = json.loads(result_path.read_text(encoding="utf-8"))
    pages = result.get("pages", [])
    if not pages:
        print("[错误] result.json 中没有页面")
        sys.exit(1)

    # 只取第1页测试
    page = pages[0]
    idx = 0
    page_title = page.get("title", "test")
    page_focus = page.get("focus", "")

    print("=" * 60)
    print("MiMo TTS + 视频合成 端到端测试")
    print(f"页面: {page_title}")
    print("=" * 60)

    VIDEO_DIR.mkdir(exist_ok=True)

    mermaid_text = page.get("mermaid_diagram", "")
    narration_text = page.get("narration_text", "")

    if not mermaid_text or not narration_text:
        print("[错误] 第1页内容为空")
        sys.exit(1)

    mermaid_text = sanitize_mermaid(mermaid_text)
    is_valid, err_msg = validate_mermaid(mermaid_text)
    print(f"[Mermaid 校验] {'通过' if is_valid else '未通过: ' + err_msg}")

    png_path = VIDEO_DIR / "test_page.png"
    audio_path = VIDEO_DIR / "test_page.wav"
    content_mp4_path = VIDEO_DIR / "test_content.mp4"
    title_png_path = VIDEO_DIR / "test_title.png"
    title_mp4_path = VIDEO_DIR / "test_title.mp4"
    final_mp4_path = VIDEO_DIR / "test_final.mp4"

    # Step 1: 渲染 Mermaid
    print("\n[Step 1/4] 渲染 Mermaid 图表...")
    png = await render_mermaid(mermaid_text, png_path)
    if not png:
        print("[失败] 图表渲染失败")
        sys.exit(1)
    print(f"[成功] 图表: {png}")

    # Step 2: MiMo TTS
    print("\n[Step 2/4] MiMo TTS 合成音频...")
    audio = await synthesize_speech_mimo(narration_text, audio_path)
    if not audio:
        print("[失败] MiMo TTS 合成失败")
        sys.exit(1)
    size_kb = audio.stat().st_size / 1024
    print(f"[成功] 音频: {audio} ({size_kb:.1f} KB)")

    # Step 3: FFmpeg 合成内容视频
    print("\n[Step 3/4] FFmpeg 合成内容视频...")
    content_mp4 = await make_video(png, audio, content_mp4_path)
    if not content_mp4:
        print("[失败] 内容视频合成失败")
        sys.exit(1)
    print(f"[成功] 内容视频: {content_mp4}")

    # Step 4: 标题 + 拼接
    print("\n[Step 4/4] 生成标题并拼接...")
    generate_title_card(
        title=page_title,
        description=page_focus,
        page_index=idx,
        total_pages=len(pages),
        output_path=title_png_path,
    )
    title_mp4 = await make_title_video(title_png_path, title_mp4_path, duration=2)
    if not title_mp4:
        print("[失败] 标题视频合成失败")
        sys.exit(1)

    final_mp4 = await concat_videos([title_mp4, content_mp4], final_mp4_path)
    if not final_mp4:
        print("[失败] 视频拼接失败")
        sys.exit(1)

    final_size_mb = final_mp4.stat().st_size / (1024 * 1024)
    print(f"\n{'=' * 60}")
    print(f"[全部通过] 端到端测试成功！")
    print(f"最终视频: {final_mp4}")
    print(f"文件大小: {final_size_mb:.1f} MB")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
