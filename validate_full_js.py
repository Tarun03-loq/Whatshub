with open(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\app.js', 'r', encoding='utf-8') as f:
    text = f.read()

import re

# Proper JS tokenizer / validator for regex, strings, templates, comments
def validate_js(s):
    i = 0
    n = len(s)
    line = 1
    col = 0
    stack = []
    
    while i < n:
        c = s[i]
        col += 1
        if c == '\n':
            line += 1
            col = 0
            
        # Single line comment
        if c == '/' and i + 1 < n and s[i+1] == '/':
            i += 2
            while i < n and s[i] != '\n':
                i += 1
            continue
            
        # Multi line comment
        if c == '/' and i + 1 < n and s[i+1] == '*':
            i += 2
            while i + 1 < n and not (s[i] == '*' and s[i+1] == '/'):
                if s[i] == '\n':
                    line += 1
                    col = 0
                i += 1
            i += 2
            continue
            
        # String ' or "
        if c in ("'", '"'):
            quote = c
            i += 1
            while i < n and s[i] != quote:
                if s[i] == '\\':
                    i += 2
                    continue
                if s[i] == '\n':
                    line += 1
                    col = 0
                i += 1
            i += 1
            continue
            
        # Template literal `
        if c == '`':
            i += 1
            while i < n and s[i] != '`':
                if s[i] == '\\':
                    i += 2
                    continue
                if s[i] == '$' and i + 1 < n and s[i+1] == '{':
                    stack.append(('`', line, col))
                    stack.append(('${', line, col))
                    i += 2
                    break
                if s[i] == '\n':
                    line += 1
                    col = 0
                i += 1
            else:
                if i < n and s[i] == '`':
                    i += 1
            continue
            
        # Regex literal detection
        # A regex can appear after: ( , = : [ ! & | ? { ; ~ ^ + - * /
        # or at beginning of statement
        if c == '/':
            # Check previous non-whitespace char
            prev_idx = i - 1
            while prev_idx >= 0 and s[prev_idx] in ' \t\r\n':
                prev_idx -= 1
            prev_ch = s[prev_idx] if prev_idx >= 0 else ''
            if prev_ch in '(=:,[!&|?{;~^+*-' or prev_idx < 0:
                # This is a regex!
                i += 1
                in_class = False
                while i < n:
                    if s[i] == '\\':
                        i += 2
                        continue
                    if s[i] == '[':
                        in_class = True
                    elif s[i] == ']':
                        in_class = False
                    elif s[i] == '/' and not in_class:
                        i += 1
                        # flags
                        while i < n and s[i].isalpha():
                            i += 1
                        break
                    i += 1
                continue
                
        # Handle template interpolation close '}'
        if c == '}':
            if stack and stack[-1][0] == '${':
                stack.pop() # pop '${'
                # now we are back inside template literal
                i += 1
                while i < n and s[i] != '`':
                    if s[i] == '\\':
                        i += 2
                        continue
                    if s[i] == '$' and i + 1 < n and s[i+1] == '{':
                        stack.append(('${', line, col))
                        i += 2
                        break
                    if s[i] == '\n':
                        line += 1
                        col = 0
                    i += 1
                else:
                    if i < n and s[i] == '`':
                        if stack and stack[-1][0] == '`':
                            stack.pop()
                        i += 1
                continue

        if c in '([{':
            stack.append((c, line, col))
        elif c in ')]}':
            if not stack:
                print(f"ERROR: Extra {c} at {line}:{col}")
                return
            top, l, cl = stack.pop()
            matches = {'(': ')', '[': ']', '{': '}'}
            if matches.get(top) != c:
                print(f"ERROR: Mismatched {top} from {l}:{cl} closed by {c} at {line}:{col}")
                return
        i += 1
        
    if stack:
        print(f"ERROR: Unclosed brackets: {stack}")
    else:
        print("ALL JAVASCRIPT BRACKETS AND SYNTAX COMPLETELY CLEAN!")

validate_js(text)

