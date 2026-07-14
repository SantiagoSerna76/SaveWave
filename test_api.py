import urllib.request
import json
req = urllib.request.Request(
    'http://127.0.0.1:5001/api/auth/firebase', 
    data=b'{"token": "fake", "action": "login"}', 
    headers={'Content-Type': 'application/json'}
)
try:
    urllib.request.urlopen(req)
except Exception as e:
    print("ERROR CAUGHT")
    print(e.read().decode('utf-8'))
