import threading
import pika
import json
from time import sleep
from flask_socketio import SocketIO

from exceptions import *

QUEUE_INPUT = 'queue_input'
QUEUE_OUTPUT = 'queue_output'
CONNEXION_URI = 'localhost'

def get_rabbitmq_handle(connection_string, max_retries=3):
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(connection_string))
        channel = connection.channel()
        print('Connexion à RabbitMQ établie')
        return channel, connection
    except Exception as e:
        print('Erreur lors de la connexion à RabbitMQ:', str(e))
        if max_retries > 0:
            sleep(5)
            return get_rabbitmq_handle(connection_string, max_retries - 1)
        else:
            raise MaxAttemptsExceededError('Nombre maximal de tentatives de connexion atteint')

def close_rabbitmq_handle(channel, connection, max_retries=3):
    try:
        channel.close()
        connection.close()
        print('Connexion à RabbitMQ fermée')
    except Exception as e:
        print('Erreur lors de la fermeture de la connexion à RabbitMQ:', str(e))
        if max_retries > 0:
            sleep(5)
            close_rabbitmq_handle(channel, connection, max_retries - 1)
        else:
            raise MaxAttemptsExceededError('Nombre maximal de tentatives de connexion atteint')

def callback(socketio, ch, method, properties, body):
    try:
        json_body = json.loads(body)
        print(f" [x] Received {json_body}")
        socket_id = json_body.get('socket_id')
        question = json_body.get('question')
        answer = json_body.get('answer')
        if socket_id and question:
            print(f" [x] Sending question to socket {socket_id}: {question}")
            socketio.emit('response', {'socket_id': socket_id, 'question': question}, room=socket_id)
        elif socket_id and answer:
            print(f" [x] Sending answer to socket {socket_id}: {answer}")
            socketio.emit('response', {'socket_id': socket_id, 'answer': answer}, room=socket_id)
    except Exception as e:
        print('Erreur lors de la réception du message:', str(e))

def output_consumer(socketio):
    channel2, connection2 = get_rabbitmq_handle(connection_string=CONNEXION_URI)
    channel2.basic_consume(queue=QUEUE_OUTPUT, auto_ack=True, on_message_callback=lambda ch, method, properties, body: callback(socketio, ch, method, properties, body))
    print('Waiting for messages...')
    channel2.start_consuming()

class RabbitMQHandler:

    def __init__(self, socketio):
        self.socketio = socketio
        try:
            self.channel, self.connection = get_rabbitmq_handle(CONNEXION_URI)
        except MaxAttemptsExceededError as e:
            print(e)
            exit(1)
        except Exception as e:
            print('Erreur lors de la connexion à RabbitMQ:', str(e))
            exit(1)

        try:
            self.channel.queue_declare(queue=QUEUE_INPUT, durable=False)
            self.channel.queue_declare(queue=QUEUE_OUTPUT, durable=False)
            print('Initialisation de la queue de messages')
        except Exception as e:
            print('Erreur lors de l\'initialisation de la queue de messages:', str(e))
            exit(1)

        try:
            self.consumer_thread = threading.Thread(target=output_consumer, args=(self.socketio,))
            self.consumer_thread.start()
        except Exception as e:
            print('Erreur lors de la création du thread de consommation:', str(e))
            exit(1)

    def send_result(self, body: dict):
        try:
            body_bytes = json.dumps(body, default=str).encode('utf-8')
            self.channel.basic_publish(exchange='',
                                       routing_key=QUEUE_OUTPUT,
                                       body=body_bytes)
        except Exception as e:
            raise SendMessageError(f'Erreur lors de l\'envoi du message: {e}')

    def dispose(self):
        print('Fermeture de la connexion à RabbitMQ')
        close_rabbitmq_handle(self.channel, self.connection)
        self.consumer_thread.join()
        print('Thread de consommation fermé')
