import time
import requests
import socketio
import json

sio = socketio.Client(ssl_verify=False)  # à changer une fois le certificat valable

API_KEY = "example_valid_key"
BASE_URL = "https://localhost:5000"
HEADERS = {'Content-Type': 'application/json'}

def get_access_token(api_key):
    response = requests.post(
        f"{BASE_URL}/api/request-token",
        headers=HEADERS,
        data=json.dumps({"API_KEY": api_key}),
        verify=False  # désactiver la vérification SSL pour les tests
    )
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        print(f"Failed to get access token: {response.json()}")
        return None

@sio.event
def connect():
    print('Connection established')
    access_token = get_access_token(API_KEY)
    if access_token:
        sio.emit('ask', {'API_KEY': API_KEY, 'question': 'What is cybersecurity?', 'access_token': access_token})
        print('Message sent: What is cybersecurity?')
    else:
        print('Could not get access token. Disconnecting...')
        sio.disconnect()

@sio.event
def status(data):
    print('Received status:', data)
    print(f"Token ID: {data.get('token_id')} has been queued")

@sio.event
def response(data):
    print('Received response:', data)
    print(f"Question received: {data.get('question')}")

@sio.event
def error(data):
    print('Received error:', data)

@sio.event
def disconnect():
    print('Disconnected from server')

# Utilisation d'une connexion WebSocket avec désactivation de la vérification SSL
sio.connect(BASE_URL, transports=['websocket'])
sio.wait()
