import requests
import json
import sys
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

files_to_audit = ['security_core.py', 'claude_brain.py', 'super_ai_routes.py']
results = []

for filename in files_to_audit:
    print(f"Auditing {filename}...", flush=True)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            code = f.read()[:6000]
    except Exception as e:
        results.append(f"=== {filename} ===\nEroare citire: {e}\n")
        continue
    
    headers = {
        'x-api-key': API_KEY,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json'
    }
    
    payload = {
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 800,
        'messages': [{
            'role': 'user',
            'content': f'''Analizează codul și oferă AUDIT CONCIS:
1. Vulnerabilități CRITICE (dacă există)
2. Bug-uri potențiale  
3. Optimizări recomandate
4. Scor calitate (1-10)

```python
{code}
```

Răspunde în română, max 200 cuvinte.'''
        }]
    }
    
    try:
        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers=headers,
            json=payload,
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            text = ""
            for block in data.get('content', []):
                if block.get('type') == 'text':
                    text += block.get('text', '')
            results.append(f"=== AUDIT: {filename} ===\n{text}\n")
        else:
            results.append(f"=== {filename} ===\nAPI Error {response.status_code}: {response.text[:200]}\n")
            
    except Exception as e:
        results.append(f"=== {filename} ===\nEroare: {e}\n")

# Save results
with open('AUDIT_RESULTS.md', 'w', encoding='utf-8') as f:
    f.write("# KELION SUPER AI - AUDIT REPORT\n\n")
    f.write("\n\n".join(results))

print("Audit complet! Vezi AUDIT_RESULTS.md", flush=True)
