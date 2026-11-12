import urllib.request, json, sys
url = 'http://127.0.0.1:5001/tasks'
try:
    with urllib.request.urlopen(url) as resp:
        data = resp.read().decode('utf-8')
        print(data)
except Exception as e:
    print('Error:', e, file=sys.stderr)

