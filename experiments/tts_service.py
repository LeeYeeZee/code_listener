"""
TTS 语音合成服务：支持 MiniMax 和 MiMo（小米）

MiniMax API:
- Endpoint: POST {base_url}/t2a_v2
- Auth: Authorization: Bearer {api_key}
- Response: data.audio 为 hex-encoded 音频数据

MiMo API:
- Endpoint: POST {base_url}/chat/completions
- Auth: Header api-key: {api_key}
- Request: model + messages + audio{format,voice}
- Response: choices[0].message.audio.data (base64 WAV)
"""
import asyncio
import base64
import binascii
from pathlib import Path
from typing import Optional
import aiohttp
import config

MINIMAX_API_KEY = getattr(config, "MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = getattr(config, "MINIMAX_BASE_URL", "https://api.minimaxi.com/v1")
MINIMAX_VOICE_ID = getattr(config, "MINIMAX_VOICE_ID", "Chinese (Mandarin)_Mature_Woman")
MINIMAX_MODEL = "speech-2.8-hd"

MIMO_API_KEY = getattr(config, "MIMO_API_KEY", "")
MIMO_BASE_URL = getattr(config, "MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_VOICE_ID = getattr(config, "MIMO_VOICE_ID", "茉莉")
MIMO_MODEL = "mimo-v2.5-tts"


def _chunk_text(text: str, max_chars: int = 3000) -> list[str]:
    """将长文本按句子边界切分为多个 chunk，每个不超过 max_chars。"""
    chunks = []
    while text:
        if len(text) <= max_chars:
            chunks.append(text)
            break
        # 在句子边界切分
        split_pos = text.rfind("。", 0, max_chars)
        if split_pos == -1:
            split_pos = text.rfind("，", 0, max_chars)
        if split_pos == -1:
            split_pos = max_chars
        chunks.append(text[:split_pos + 1])
        text = text[split_pos + 1:]
    return chunks


async def synthesize_speech(
    text: str,
    output_path: Path,
    voice_id: str = MINIMAX_VOICE_ID,
    speed: int = 1,
    vol: int = 1,
    pitch: int = 0,
) -> Optional[Path]:
    """
    调用 MiniMax TTS API 将文本合成为音频（MP3）。
    
    Args:
        text: 要朗读的文本
        output_path: 输出音频文件路径 (.mp3)
        voice_id: 音色ID
        speed: 语速 (整数 0-10, 默认1)
        vol: 音量 (整数 0-10, 默认1)
        pitch: 音调 (整数 -12 到 12, 默认0)
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not MINIMAX_API_KEY:
        print(f"      [TTS失败] MINIMAX_API_KEY 未配置")
        return None
    
    # MiniMax TTS 对单段文本有长度限制，分段处理
    chunks = _chunk_text(text)
    audio_parts = []
    
    headers = {
        "Authorization": f"Bearer {MINIMAX_API_KEY}",
        "Content-Type": "application/json",
    }
    
    tts_url = f"{MINIMAX_BASE_URL}/t2a_v2"
    
    for chunk_idx, chunk_text in enumerate(chunks):
        payload = {
            "model": MINIMAX_MODEL,
            "text": chunk_text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
                "vol": vol,
                "pitch": pitch,
            },
            "audio_setting": {
                "format": "mp3",
                "sample_rate": 32000,
            },
        }
        
        last_error = None
        for attempt in range(3):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        tts_url,
                        headers=headers,
                        json=payload,
                        timeout=aiohttp.ClientTimeout(total=120),
                    ) as resp:
                        resp_data = await resp.json()
                        
                        # 检查响应状态
                        base_resp = resp_data.get("base_resp", {})
                        status_code = base_resp.get("status_code", 0)
                        if status_code != 0:
                            status_msg = base_resp.get("status_msg", "unknown error")
                            raise RuntimeError(f"MiniMax TTS API error {status_code}: {status_msg}")
                        
                        # 提取音频数据（hex encoded）
                        audio_hex = resp_data.get("data", {}).get("audio", "")
                        if not audio_hex:
                            raise RuntimeError("MiniMax TTS API returned no audio data")
                        
                        audio_bytes = binascii.unhexlify(audio_hex)
                        audio_parts.append(audio_bytes)
                        print(f"      [TTS chunk {chunk_idx + 1}/{len(chunks)} OK] {len(audio_bytes)} bytes")
                        break
                        
            except Exception as e:
                last_error = e
                wait = 2 ** attempt
                print(f"      [TTS重试 {attempt + 1}/3] chunk {chunk_idx + 1}: {e}, {wait}s后重试...")
                await asyncio.sleep(wait)
        else:
            print(f"      [TTS失败] chunk {chunk_idx + 1}: {last_error}")
            return None
    
    # 合并所有音频片段
    combined_audio = b"".join(audio_parts)
    output_path.write_bytes(combined_audio)
    size_kb = len(combined_audio) / 1024
    print(f"      [TTS合成成功] {output_path} ({size_kb:.1f} KB)")
    return output_path


async def synthesize_speech_mimo(
    text: str,
    output_path: Path,
    voice_id: str = MIMO_VOICE_ID,
    instruction: str = "",
) -> Optional[Path]:
    """
    调用 MiMo TTS API 将文本合成为音频（WAV）。
    
    Args:
        text: 要朗读的文本
        output_path: 输出音频文件路径 (.wav)
        voice_id: 音色ID（冰糖/茉莉/苏打/白桦）
        instruction: 自然语言风格控制（可选）
    
    Returns:
        成功返回 output_path，失败返回 None
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not MIMO_API_KEY:
        print(f"      [TTS失败] MIMO_API_KEY 未配置")
        return None
    
    headers = {
        "Content-Type": "application/json",
        "api-key": MIMO_API_KEY,
    }
    
    url = f"{MIMO_BASE_URL}/chat/completions"
    
    messages = []
    if instruction:
        messages.append({"role": "user", "content": instruction})
    messages.append({"role": "assistant", "content": text})
    
    payload = {
        "model": MIMO_MODEL,
        "messages": messages,
        "audio": {
            "format": "wav",
            "voice": voice_id,
        },
    }
    
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as resp:
                    resp_text = await resp.text()
                    
                    if resp.status >= 400:
                        print(f"      [TTS重试 {attempt + 1}/3] HTTP {resp.status}: {resp_text[:200]}")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    resp_data = await resp.json()
                    
                    # 提取 base64 音频数据
                    choice0 = resp_data["choices"][0]
                    msg = choice0.get("message") or choice0.get("delta")
                    audio_b64 = msg.get("audio", {}).get("data", "")
                    if not audio_b64:
                        # fallback: 直接取 data 字段
                        audio_b64 = resp_data.get("data", "")
                    
                    if not audio_b64:
                        print(f"      [TTS重试 {attempt + 1}/3] 响应中无音频数据")
                        await asyncio.sleep(2 ** attempt)
                        continue
                    
                    audio_bytes = base64.b64decode(audio_b64)
                    output_path.write_bytes(audio_bytes)
                    size_kb = len(audio_bytes) / 1024
                    print(f"      [TTS合成成功] {output_path} ({size_kb:.1f} KB)")
                    return output_path
                    
        except Exception as e:
            wait = 2 ** attempt
            print(f"      [TTS重试 {attempt + 1}/3] {e}, {wait}s后重试...")
            await asyncio.sleep(wait)
    
    print(f"      [TTS失败] MiMo TTS 最终失败")
    return None
