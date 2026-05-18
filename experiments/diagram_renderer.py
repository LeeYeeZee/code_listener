"""
Mermaid 图表渲染：将 Mermaid 文本渲染为高清 PNG
"""
import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

async def render_mermaid(
    mermaid_text: str,
    output_path: Path,
    width: int = 1080,
    height: int = 1920,
    bg_color: str = "#ffffff",
) -> Optional[Path]:
    """
    使用 mmdc (Mermaid CLI) 将 Mermaid 文本渲染为 PNG。
    
    Args:
        mermaid_text: Mermaid 图表语法字符串
        output_path: 输出 PNG 文件路径
        width: 输出宽度
        height: 输出高度
        bg_color: 背景色
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 写入临时 mmd 文件
    input_file = output_path.with_suffix(".mmd")
    input_file.write_text(mermaid_text, encoding="utf-8")
    
    cmd = [
        "mmdc",
        "-i", str(input_file),
        "-o", str(output_path),
        "-b", bg_color,
        "-w", str(width),
        "-H", str(height),
    ]
    
    try:
        # Windows 下使用 subprocess_shell 确保能找到 PATH 中的 mmdc
        # 设置 UTF-8 环境避免编码错误
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        proc = await asyncio.create_subprocess_shell(
            " ".join(f'"{c}"' if " " in c else c for c in cmd),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
        
        if proc.returncode != 0:
            try:
                err = stderr.decode("utf-8", errors="ignore")[:500]
            except Exception:
                err = str(stderr)[:500]
            # 过滤掉可能导致 Windows 控制台编码错误的 Unicode 私有区字符
            err = err.replace('\ufb02', 'fi').replace('\ufb01', 'fi')
            print(f"      [Mermaid渲染失败] {err}")
            return None
        
        if output_path.exists():
            print(f"      [Mermaid渲染成功] {output_path}")
            return output_path
        else:
            print(f"      [Mermaid渲染失败] 输出文件未生成")
            return None
            
    except asyncio.TimeoutError:
        print(f"      [Mermaid渲染失败] 超时")
        return None
    except Exception as e:
        print(f"      [Mermaid渲染失败] {e}")
        return None
    finally:
        # 清理临时文件
        if input_file.exists():
            input_file.unlink()
