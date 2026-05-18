"""
LLM 调用封装：支持 OpenAI 兼容接口，带指数退避重试
"""
import asyncio
import json
from typing import AsyncIterator
import aiohttp
import config

async def chat_completion(
    messages: list[dict],
    temperature: float = 0.3,
    stream: bool = False,
    response_format: dict | None = None,
    max_retries: int = 3,
    max_tokens: int | None = None,
) -> str:
    """
    异步调用 LLM Chat Completion，带指数退避重试。
    """
    if not config.LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY not set. Please check your .env file.")

    headers = {
        "Authorization": f"Bearer {config.LLM_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": stream,
    }
    if response_format:
        payload["response_format"] = response_format
    if max_tokens:
        payload["max_tokens"] = max_tokens

    last_error = None
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{config.LLM_BASE_URL}/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=600),
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        raise RuntimeError(f"LLM API error {resp.status}: {text}")
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
        except Exception as e:
            last_error = e
            wait = 2 ** attempt  # 指数退避: 1s, 2s, 4s
            err_type = type(e).__name__
            err_msg = str(e) if str(e) else "(empty error message)"
            print(f"      [重试 {attempt + 1}/{max_retries}] LLM调用失败 [{err_type}]: {err_msg}, {wait}s后重试...")
            await asyncio.sleep(wait)
    
    raise last_error
