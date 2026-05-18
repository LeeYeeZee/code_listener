"""
标题卡片生成器：用 Pillow 生成纯白极简风格的标题卡片
"""
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

WIDTH = 1080
HEIGHT = 1920
BG_COLOR = "#ffffff"
TITLE_COLOR = "#1a1a1a"
DESC_COLOR = "#555555"
PAGE_NUM_COLOR = "#888888"
LINE_COLOR = "#e0e0e0"


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """获取中文字体，优先微软雅黑。"""
    font_paths = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in font_paths:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    # 回退到默认字体
    return ImageFont.load_default()


def generate_title_card(
    title: str,
    description: str,
    page_index: int,
    total_pages: int,
    output_path: Path,
) -> Path:
    """
    生成一页的标题卡片图片。
    
    布局（竖版 1080×1920）：
    - 顶部留白约 35%
    - 页码（小号浅灰）
    - 标题（大号粗体黑色，居中）
    - 聚焦描述（中号深灰）
    - 底部细灰线 + 页码指示器
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    img = Image.new("RGB", (WIDTH, HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)
    
    # 字体
    font_page = _get_font(32)
    font_title = _get_font(64, bold=True)
    font_desc = _get_font(40)
    
    # 1. 页码（上方）
    page_text = f"{page_index + 1:02d} / {total_pages:02d}"
    bbox = draw.textbbox((0, 0), page_text, font=font_page)
    text_w = bbox[2] - bbox[0]
    x = (WIDTH - text_w) // 2
    y = HEIGHT // 3 - 60
    draw.text((x, y), page_text, fill=PAGE_NUM_COLOR, font=font_page)
    
    # 2. 标题（中间，自动换行处理）
    # 简单换行：如果标题太长，按字符数截断换行
    max_chars_per_line = 12
    lines = []
    current = ""
    for char in title:
        current += char
        if len(current) >= max_chars_per_line:
            lines.append(current)
            current = ""
    if current:
        lines.append(current)
    
    # 如果没有换行（标题较短），直接一行
    if len(lines) == 0:
        lines = [title]
    
    line_height = 80
    total_text_h = len(lines) * line_height
    start_y = (HEIGHT // 2) - (total_text_h // 2) - 40
    
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_title)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = start_y + i * line_height
        draw.text((x, y), line, fill=TITLE_COLOR, font=font_title)
    
    # 3. 聚焦描述（标题下方）
    if description:
        bbox = draw.textbbox((0, 0), description, font=font_desc)
        text_w = bbox[2] - bbox[0]
        x = (WIDTH - text_w) // 2
        y = start_y + total_text_h + 40
        draw.text((x, y), description, fill=DESC_COLOR, font=font_desc)
    
    # 4. 底部细灰线
    line_y = HEIGHT - 200
    draw.line([(120, line_y), (WIDTH - 120, line_y)], fill=LINE_COLOR, width=2)
    
    # 5. 底部页码指示器（小圆点）
    dot_radius = 8
    dot_spacing = 28
    total_dots_w = total_pages * dot_spacing - (dot_spacing - dot_radius * 2)
    start_x = (WIDTH - total_dots_w) // 2
    
    for i in range(total_pages):
        cx = start_x + i * dot_spacing + dot_radius
        cy = line_y + 50
        color = TITLE_COLOR if i == page_index else LINE_COLOR
        draw.ellipse(
            [(cx - dot_radius, cy - dot_radius), (cx + dot_radius, cy + dot_radius)],
            fill=color,
        )
    
    img.save(output_path, "PNG")
    return output_path
