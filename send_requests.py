import json, sys
import urllib.request

def post(url, data):
    req = urllib.request.Request(url, data=json.dumps(data).encode('utf-8'), headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()

# Add group to whitelist and activate
add_resp = post('http://127.0.0.1:5001/groups/add', {'jid': '120363028192847@g.us', 'name': 'College CSE Final Year', 'icon': '📚'})
print('Add group response:', add_resp)

# Send simulated message
msg = {
    'chatJid': '120363028192847@g.us',
    'groupName': 'College CSE Final Year',
    'sender': 'Prof. Ramanathan',
    'message': 'Final submission for Cloud Computing Lab Records due tomorrow at 4:00 PM. No extensions.'
}
recv_resp = post('http://127.0.0.1:5001/receive', msg)
print('Receive response:', recv_resp)

