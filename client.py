import requests
import json
import socketio

from rabbitmq_handler import RabbitMQHandler
#import warnings
#import urllib3

#urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


sio = socketio.Client(ssl_verify=False)

API_KEY = "example_valid_key"
BASE_URL = "https://localhost:5000"
HEADERS = {'Content-Type': 'application/json'}

rabbitmq_handler = RabbitMQHandler()

def get_access_token(api_key):
    response = requests.post(
        f"{BASE_URL}/api/request-token",
        headers=HEADERS,
        data=json.dumps({"API_KEY": api_key}),
        verify=False
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get access token: {response.json()}")
        return None

def print_queue(queue_name):
    response = requests.post(
        f"{BASE_URL}/api/print_queue",
        headers=HEADERS,
        data=json.dumps({"queue_name": queue_name}),
        verify=False
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get messages: {response.json()}")
        return None

def start_processing_queue():
    response = requests.post(
        f"{BASE_URL}/api/process_queue",
        headers=HEADERS,
        data=json.dumps({}),
        verify=False
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to start processing queue: {response.json()}")
        return None

def start_processing_output_queue():
    response = requests.post(
        f"{BASE_URL}/api/process_output_queue",
        headers=HEADERS,
        data=json.dumps({}),
        verify=False
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to start processing output queue: {response.json()}")
        return None

def send_question(access_token, question):
    sio.emit('send_question', {'access_token': access_token, 'question': question})


@sio.event
def connect():
    print('Connection established')
    response = get_access_token(API_KEY)
    access_token = response['access_token'] if response else None
    if access_token:
        print(f"Access token obtained: {access_token}")
        send_question(access_token, question='what is a Mittre Attack?')
        send_question(access_token, question='how to secure a windows system ?')
        start_processing_queue()
        print_queue('queue_input')
        start_processing_output_queue()
        print_queue('queue_output')
    else:
        print('Could not get access token. Disconnecting...')
        sio.disconnect()

@sio.event
def sending_question_status(data):
    print(f"Received sending question status: {data}")

@sio.event
def response(data):
    print(f"Received response: {data}")

@sio.event
def disconnect():
    print('Disconnected from server')

def main():
    sio.connect(BASE_URL, transports=['websocket'])
    sio.wait()

if __name__ == "__main__":
    main()
