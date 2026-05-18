import asyncio, aiohttp, os, time
from dotenv import load_dotenv
load_dotenv()

async def test():
    key = os.getenv('LLM_API_KEY')
    url = os.getenv('LLM_BASE_URL') + '/chat/completions'
    model = os.getenv('LLM_MODEL')
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

    # 测试1: 带 response_format
    print('=== Test 1: with response_format ===')
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'Return JSON only.'},
            {'role': 'user', 'content': 'Return {"hello": "world"}'}
        ],
        'temperature': 0.3,
        'response_format': {'type': 'json_object'}
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            print(f'Status: {resp.status}')
            text = await resp.text()
            print(f'Response: {text[:500]}')

    # 测试2: 长 prompt（模拟 storyboard 的长度）
    print()
    print('=== Test 2: long prompt (70KB user + 5KB system) ===')
    long_content = 'A' * 70000
    payload2 = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': 'You are a technical architect. ' + 'B' * 5000},
            {'role': 'user', 'content': long_content + '\n\nSummarize in 10 words.'}
        ],
        'temperature': 0.3,
        'max_tokens': 50
    }
    start = time.time()
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload2, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            elapsed = time.time() - start
            print(f'Status: {resp.status}, Time: {elapsed:.1f}s')
            text = await resp.text()
            print(f'Response len: {len(text)}')
            print(f'Response: {text[:500]}')

asyncio.run(test())
