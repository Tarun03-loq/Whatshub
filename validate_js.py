with open(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\app.js', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Let's verify bracket matching properly
stack = []
line = 1
col = 0
in_s = None
escape = False

i = 0
n = len(text)
errors = []

while i < n:
    c = text[i]
    col += 1
    if c == '\n':
        line += 1
        col = 0

    if in_s:
        if escape:
            escape = False
        elif c == '\\':
            escape = True
        elif in_s == '//':
            if c == '\n':
                in_s = None
        elif in_s == '/*':
            if c == '*' and i + 1 < n and text[i+1] == '/':
                in_s = None
                i += 1
        elif c == in_s:
            in_s = None
    else:
        if c == '/' and i + 1 < n and text[i+1] == '/':
            in_s = '//'
            i += 1
        elif c == '/' and i + 1 < n and text[i+1] == '*':
            in_s = '/*'
            i += 1
        elif c in ('"', "'", '`'):
            in_s = c
        elif c in '([{':
            stack.append((c, line, col))
        elif c in ')]}':
            if not stack:
                errors.append(f"Extra closing '{c}' at {line}:{col}")
            else:
                top, l, cl = stack.pop()
                expected = {'(':')', '[':']', '{':'}'}[top]
                if expected != c:
                    errors.append(f"Mismatched {top} from {l}:{cl} closed by {c} at {line}:{col}")
    i += 1

if stack:
    errors.append(f"Unclosed open brackets ({len(stack)} remaining). Top items: {stack[-5:]}")

if errors:
    print("ERRORS FOUND:")
    for err in errors:
        print(" ", err)
else:
    print("SUCCESS: app.js syntax and brackets are 100% valid!")

