"""
实验脚本配置
"""
import os
from dotenv import load_dotenv

load_dotenv()

LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-v4-pro")

# 代码预处理参数
MAX_FILE_SIZE = 30 * 1024  # 30KB，超过则截断
MAX_FILES_FOR_SUMMARY = 40  # 大纲生成时最多传入多少文件（大项目需要更多上下文）
MAX_LINES_PER_FILE = 60     # 每文件最多提取多少行

# 叙事引擎配置（已废弃固定时长，改由 Prompt 让 LLM 根据概念复杂度自主决定）
# NARRATION_TARGET_SECONDS = int(os.getenv("NARRATION_TARGET_SECONDS", "75"))

# 视频输出配置（竖版短视频 9:16）
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
VIDEO_RESOLUTION = f"{VIDEO_WIDTH}x{VIDEO_HEIGHT}"

# MiniMax TTS 配置
MINIMAX_API_KEY = os.getenv("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_VOICE_ID = os.getenv("MINIMAX_VOICE_ID", "Chinese (Mandarin)_Mature_Woman")

# MiMo TTS 配置（小米）
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_VOICE_ID = os.getenv("MIMO_VOICE_ID", "茉莉")  # 冰糖/茉莉/苏打/白桦
