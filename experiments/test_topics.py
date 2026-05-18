import asyncio, aiohttp, os, json
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('LLM_API_KEY')
url = os.getenv('LLM_BASE_URL') + '/chat/completions'
model = os.getenv('LLM_MODEL')

system_prompt = """你是一位技术文档架构师。基于代码文件列表，列出需要讲解的技术主题。

要求：
1. 每个核心文件至少对应一个主题
2. 输出 JSON 数组
3. 每个元素包含：topic_id, title, focus, scope_files, rationale
"""

user_prompt = """核心文件列表：
  - db/db_impl.cc
  - db/db_impl.h
  - db/memtable.cc
  - db/skiplist.h
  - db/write_batch.cc
  - db/version_set.cc
  - table/table.cc
  - table/block.cc
  - util/cache.cc

请列出所有需要讲解的技术主题。"""

async def test():
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    
    # Test 1: with response_format
    print('=== Test 1: with response_format ===')
    payload = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0.3,
        'response_format': {'type': 'json_object'},
        'max_tokens': 2000,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            print(f'Status: {resp.status}')
            print(f'Response: {text[:1000]}')
    
    # Test 2: without response_format
    print()
    print('=== Test 2: without response_format ===')
    payload2 = {
        'model': model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ],
        'temperature': 0.3,
        'max_tokens': 2000,
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload2, timeout=aiohttp.ClientTimeout(total=120)) as resp:
            text = await resp.text()
            print(f'Status: {resp.status}')
            print(f'Response: {text[:1000]}')

asyncio.run(test())
