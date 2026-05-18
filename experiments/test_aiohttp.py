import asyncio, aiohttp, os, time
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('LLM_API_KEY')
url = os.getenv('LLM_BASE_URL') + '/chat/completions'
model = os.getenv('LLM_MODEL')

code_summary = open('output/code_summary.txt', encoding='utf-8').read()[:5000]

payload = {
    'model': model,
    'messages': [
        {'role': 'system', 'content': 'You are a technical architect.'},
        {'role': 'user', 'content': code_summary + '\n\nSummarize in 3 bullet points.'}
    ],
    'temperature': 0.3,
    'max_tokens': 200
}

headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

async def test_with_connector():
    print('Test 1: default connector')
    start = time.time()
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                elapsed = time.time() - start
                print(f'  Status: {resp.status}, Time: {elapsed:.1f}s')
                text = await resp.text()
                print(f'  Response: {text[:300]}')
    except Exception as e:
        elapsed = time.time() - start
        print(f'  Error after {elapsed:.1f}s: {type(e).__name__}: {e}')

    print()
    print('Test 2: TCPConnector with force_close')
    start = time.time()
    try:
        connector = aiohttp.TCPConnector(force_close=True, enable_cleanup_closed=True)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
                elapsed = time.time() - start
                print(f'  Status: {resp.status}, Time: {elapsed:.1f}s')
                text = await resp.text()
                print(f'  Response: {text[:300]}')
    except Exception as e:
        elapsed = time.time() - start
        print(f'  Error after {elapsed:.1f}s: {type(e).__name__}: {e}')

asyncio.run(test_with_connector())
