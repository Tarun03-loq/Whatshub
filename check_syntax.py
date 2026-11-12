import re

with open(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\app.js', 'r', encoding='utf-8') as f:
    code = f.read()

# Let's check from line 1180 onwards
print("Line 1180+ content:")
lines = code.splitlines()
for i in range(1178, len(lines)):
    print(f"{i+1}: {lines[i]}")

