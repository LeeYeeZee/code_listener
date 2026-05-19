"""
MiMo TTS 连通性测试
"""
import asyncio
import tempfile
from pathlib import Path

from tts_service import synthesize_speech_mimo
import config

TEST_TEXT = "你好，我是 Code Listener 的语音助手。这段语音用于测试 MiMo TTS 的连通性。"


async def main():
    print("=" * 60)
    print("MiMo TTS 连通性测试")
    print("=" * 60)
    print(f"Base URL: {config.MIMO_BASE_URL}")
    print(f"Voice ID: {config.MIMO_VOICE_ID}")
    print(f"API Key:  {config.MIMO_API_KEY[:20]}..." if config.MIMO_API_KEY else "未配置")
    print()

    if not config.MIMO_API_KEY:
        print("[错误] MIMO_API_KEY 未配置，请在 .env 中设置")
        return

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "test_mimo.wav"
        print(f"[测试] 合成文本: {TEST_TEXT}")
        print(f"[测试] 输出路径: {output_path}")
        print()

        result = await synthesize_speech_mimo(TEST_TEXT, output_path)

        if result:
            size_kb = result.stat().st_size / 1024
            print(f"\n[成功] MiMo TTS 连通！")
            print(f"       文件: {result}")
            print(f"       大小: {size_kb:.1f} KB")
        else:
            print(f"\n[失败] MiMo TTS 无法连通，请检查配置")


if __name__ == "__main__":
    asyncio.run(main())
