"""
视频合成：使用 FFmpeg 将静态图 + 音频合成为 MP4 视频
"""
import asyncio
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, List
import config


async def _run_ffmpeg(cmd: list, timeout: int = 120) -> tuple[int, bytes, bytes]:
    """异步运行 FFmpeg 命令并返回结果。"""
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise
    return proc.returncode, stdout, stderr


async def make_video(
    image_path: Path,
    audio_path: Path,
    output_path: Path,
    resolution: str = config.VIDEO_RESOLUTION,
    fps: int = 30,
) -> Optional[Path]:
    """
    使用 FFmpeg 将静态图和音频合成为视频。
    
    视频始终保持展示同一张图，以音频长度为准。
    
    Args:
        image_path: 输入图片路径 (.png/.jpg)
        audio_path: 输入音频路径 (.mp3/.wav)
        output_path: 输出视频路径 (.mp4)
        resolution: 输出分辨率
        fps: 帧率
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    w, h = resolution.split("x")
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-i", str(audio_path),
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        str(output_path),
    ]
    
    try:
        rc, _, stderr = await _run_ffmpeg(cmd)
        if rc != 0:
            err = stderr.decode("utf-8", errors="ignore")[:500]
            print(f"      [FFmpeg合成失败] {err}")
            return None
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"      [FFmpeg合成成功] {output_path} ({size_mb:.1f} MB)")
            return output_path
        else:
            print(f"      [FFmpeg合成失败] 输出文件未生成")
            return None
            
    except asyncio.TimeoutError:
        print(f"      [FFmpeg合成失败] 超时")
        return None
    except FileNotFoundError:
        print(f"      [FFmpeg合成失败] ffmpeg 未安装")
        return None


async def make_title_video(
    image_path: Path,
    output_path: Path,
    duration: int = 2,
    resolution: str = config.VIDEO_RESOLUTION,
) -> Optional[Path]:
    """
    生成标题视频（固定时长，带静音音频轨道，用于拼接）。
    
    Args:
        image_path: 标题卡片图片路径
        output_path: 输出视频路径
        duration: 视频时长（秒），默认 2
        resolution: 输出分辨率
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    w, h = resolution.split("x")
    cmd = [
        "ffmpeg",
        "-y",
        "-loop", "1",
        "-i", str(image_path),
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=stereo",
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", str(duration),
        "-pix_fmt", "yuv420p",
        "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black",
        str(output_path),
    ]
    
    try:
        rc, _, stderr = await _run_ffmpeg(cmd)
        if rc != 0:
            err = stderr.decode("utf-8", errors="ignore")[:500]
            print(f"      [FFmpeg标题视频失败] {err}")
            return None
        
        if output_path.exists():
            print(f"      [FFmpeg标题视频成功] {output_path}")
            return output_path
        else:
            print(f"      [FFmpeg标题视频失败] 输出文件未生成")
            return None
            
    except asyncio.TimeoutError:
        print(f"      [FFmpeg标题视频失败] 超时")
        return None
    except FileNotFoundError:
        print(f"      [FFmpeg标题视频失败] ffmpeg 未安装")
        return None


async def concat_videos(
    video_paths: List[Path],
    output_path: Path,
) -> Optional[Path]:
    """
    使用 FFmpeg filter_complex concat 拼接多个视频。
    
    支持不同编码参数的输入（会自动统一重编码），
    适合拼接标题片段（可能有静音音频）和内容片段。
    
    Args:
        video_paths: 待拼接的视频路径列表
        output_path: 输出视频路径
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    if len(video_paths) < 2:
        print(f"      [拼接跳过] 视频数量不足（{len(video_paths)} 个）")
        return video_paths[0] if video_paths else None
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    n = len(video_paths)
    inputs = []
    filter_parts = []
    for i, p in enumerate(video_paths):
        inputs.extend(["-i", str(p)])
        filter_parts.append(f"[{i}:v][{i}:a]")
    filter_parts.append(f"concat=n={n}:v=1:a=1[outv][outa]")
    filter_complex = "".join(filter_parts)
    
    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[outv]",
        "-map", "[outa]",
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    
    try:
        rc, _, stderr = await _run_ffmpeg(cmd, timeout=300)
        
        if rc != 0:
            err = stderr.decode("utf-8", errors="ignore")[:500]
            print(f"      [FFmpeg拼接失败] {err}")
            return None
        
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"      [FFmpeg拼接成功] {output_path} ({size_mb:.1f} MB)")
            return output_path
        else:
            print(f"      [FFmpeg拼接失败] 输出文件未生成")
            return None
            
    except asyncio.TimeoutError:
        print(f"      [FFmpeg拼接失败] 超时")
        return None
    except FileNotFoundError:
        print(f"      [FFmpeg拼接失败] ffmpeg 未安装")
        return None
