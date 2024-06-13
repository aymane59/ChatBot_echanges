import warnings
import urllib3

warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)

import requests
import json
import socketio

from rabbitmq_handler import RabbitMQHandler

sio = socketio.Client(ssl_verify=False)

API_KEY = "UwHtq7SkGS51u9DvKEAGM6e2E2izoCYTrgBeVNql1rpsWyfRkxSGx44q7C6YEdiiyOPR4HwFT8N9D0h7eq4HfhRx0x0LlvhP3Ps1B9ra7EfWwYUy8DkWOFwusZQFbIv2"
BASE_URL = "http://localhost:5000"
HEADERS = {'Content-Type': 'application/json'}

rabbitmq_handler = RabbitMQHandler()


def get_access_token(api_key):
    response = requests.post(
        f"{BASE_URL}/api/request_token",
        headers=HEADERS,
        data=json.dumps({"API_KEY": api_key}),
        verify=False
    )
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get access token: {response.json()}")
        return None


# def print_queue(queue_name):
#     response = requests.post(
#         f"{BASE_URL}/api/print_queue",
#         headers=HEADERS,
#         data=json.dumps({"queue_name": queue_name}),
#         verify=False
#     )
#     if response.status_code == 200:
#         return response.json()
#     else:
#         print(f"Failed to get messages: {response.json()}")
#         return None


def send_message(access_token, message):
    sio.emit('message', {'access_token': access_token, 'message': message})


@sio.event
def connect():
    print('Connection established')
    response = get_access_token(API_KEY)
    access_token = response['access_token'] if response else None
    if access_token:
        print(f"Access token obtained: {access_token}")
        send_message(access_token, message='what is a Mittre Attack?')
        send_message(access_token, message='how to secure a windows system ?')
        # print_queue('queue_input')
        # print_queue('queue_output')
    else:
        print('Could not get access token. Disconnecting...')
        sio.disconnect()


@sio.event
def loading(data):
    print(f"Received loading status: {data}")


@sio.event
def error(data):
    print(f"Received error status: {data}")


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
