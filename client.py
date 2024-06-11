import requests
import json
import socketio

sio = socketio.Client(ssl_verify=False)  # à changer une fois le certificat valable

API_KEY = "example_valid_key"
BASE_URL = "https://localhost:5000"
HEADERS = {'Content-Type': 'application/json'}
socket_id = None

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

def send_question(access_token, question, socket_id):
    response = requests.post(
        f"{BASE_URL}/api/socket/send_question",
        headers=HEADERS,
        data=json.dumps({"access_token": access_token, "question": question, "socket_id": socket_id}),
        verify=False  # désactiver la vérification SSL pour les tests
    )
    if response.status_code == 200:
        response_data = response.json()
        if response_data.get('status') == 'loading':
            print(f"Question sent: {question}")
            print(f"Received response: {response_data}")
        else:
            print(f"Question not sent. Status: {response_data.get('status')}")
    else:
        print(f"Failed to send question: {response.json()}")

@sio.event
def connect():
    global socket_id
    print('Connection established')
    socket_id = sio.sid
    access_token = get_access_token(API_KEY)
    if access_token:
        print(f"Access token obtained: {access_token}")
        send_question(access_token, "What is Fishing?", socket_id)
    else:
        print('Could not get access token. Disconnecting...')
        sio.disconnect()

@sio.event
def disconnect():
    print('Disconnected from server')

def main():
    sio.connect(BASE_URL, transports=['websocket'])
    sio.wait()

if __name__ == "__main__":
    main()
