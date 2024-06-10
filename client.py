import socketio

sio = socketio.Client(ssl_verify=False) # a changer une fois le certificat valable

@sio.event
def connect():
    print('Connection established')
    sio.emit('ask', {'API_KEY': 'example_valid_key', 'question': 'What is cybersecurity?'})
    print('Message sent: What is cybersecurity?')

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
sio.connect('https://localhost:5000', transports=['websocket'])
sio.wait()
