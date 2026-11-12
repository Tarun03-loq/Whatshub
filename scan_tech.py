import re

files = [
    r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\index.html',
    r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\app.js',
]

keywords = ['gemma', 'ollama', 'neonize', 'sqlite', 'hacknova', 'segno']

for p in files:
    with open(p, 'r', encoding='utf-8') as f:
        content = f.read()
    print('=== File:', p)
    for kw in keywords:
        matches = list(re.finditer(re.escape(kw), content, re.IGNORECASE))
        if matches:
            print(f'  Found "{kw}": {len(matches)} times')
            for m in matches[:3]:
                start = max(0, m.start() - 30)
                end = min(len(content), m.end() + 30)
                print(f'    ...{repr(content[start:end])}...')

