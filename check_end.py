with open(r'C:\Users\tarun\.gemini\antigravity\scratch\Whatshub\app.js', 'r', encoding='utf-8') as f:
    lines = f.readlines()

print("Line 1150-1200:")
for i in range(1150, len(lines)):
    print(f"{i+1}: {lines[i]}", end="")

