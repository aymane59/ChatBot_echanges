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

@sio.event
def connect():
    global socket_id
    print('Connection established')
    socket_id = sio.sid
    access_token = get_access_token(API_KEY)
    if access_token:
        print(f"Access token obtained: {access_token}")
        send_question(access_token, "What is Fishing?", socket_id)
        send_question(access_token, "What is cybersecurity?", socket_id)
        send_question(access_token, "How does machine learning work?", socket_id)
    else:
        print('Could not get access token. Disconnecting...')
        sio.disconnect()

@sio.event
def disconnect():
    print('Disconnected from server')

@sio.event
def response(data):
    print('Received response:', data)
    status = data.get('status')
    answer = data.get('answer')
    if status and answer:
        print(f"Status: {status}, Answer: {answer}")

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
            # Traiter la queue après avoir envoyé chaque question
            process_queue()
            return_answer()
        else:
            print(f"Question not sent. Status: {response_data.get('status')}")
    else:
        print(f"Failed to send question: {response.json()}")

def process_queue():
    response = requests.post(
        f"{BASE_URL}/api/socket/process_queue",
        headers=HEADERS,
        verify=False  # désactiver la vérification SSL pour les tests
    )
    if response.status_code == 200:
        response_data = response.json()
        print("Queue processed successfully.")
        print(f"Received response: {response_data}")
    else:
        try:
            print(f"Failed to process queue: {response.json()}")
        except ValueError:
            print(f"Failed to process queue. Status code: {response.status_code}")

def return_answer():
    response = requests.post(
        f"{BASE_URL}/api/socket/return_answer",
        headers=HEADERS,
        verify=False  # désactiver la vérification SSL pour les tests
    )
    if response.status_code == 200:
        response_data = response.json()
        for res in response_data:
            print(f"Answers processed successfully. Status: {res['status']}, Answer: {res['answer']}")
    else:
        try:
            print(f"Failed to process answers: {response.json()}")
        except ValueError:
            print(f"Failed to process answers. Status code: {response.status_code}")

def main():
    sio.connect(BASE_URL, transports=['websocket'])
    sio.wait()

if __name__ == "__main__":
    main()
