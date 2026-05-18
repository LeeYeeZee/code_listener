import os, time, json
from dotenv import load_dotenv
load_dotenv()

key = os.getenv('LLM_API_KEY')
url = os.getenv('LLM_BASE_URL') + '/chat/completions'
model = os.getenv('LLM_MODEL')

code_summary = open('output/code_summary.txt', encoding='utf-8').read()[:5000]

system_prompt = "You are a technical architect. Return JSON only."
user_prompt = f"Summarize this code in 3 bullet points:\n{code_summary}"

payload = {
    'model': model,
    'messages': [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ],
    'temperature': 0.3,
    'max_tokens': 200
}

import requests
headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}

print(f'Model: {model}')
print(f'URL: {url}')
print(f'Prompt length: {len(system_prompt) + len(user_prompt)} chars')
print('Sending request...')

start = time.time()
try:
    resp = requests.post(url, headers=headers, json=payload, timeout=(10, 120))
    elapsed = time.time() - start
    print(f'Status: {resp.status_code}, Time: {elapsed:.1f}s')
    print(f'Response: {resp.text[:800]}')
except Exception as e:
    elapsed = time.time() - start
    print(f'Error after {elapsed:.1f}s: {type(e).__name__}: {e}')
