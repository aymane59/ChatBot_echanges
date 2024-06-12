import random
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


class RabbitMQHandler:

    def __init__(self, socketio=None):
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
            self.purge_queue(QUEUE_INPUT)
            self.purge_queue(QUEUE_OUTPUT)
            print('Queues vidées')
        except Exception as e:
            print('Erreur lors de l\'initialisation de la queue de messages:', str(e))
            exit(1)

    def send_to_queue(self, body: dict, queue_name):
        try:
            body_bytes = json.dumps(body, default=str).encode('utf-8')
            self.channel.basic_publish(exchange='',
                                       routing_key=queue_name,
                                       body=body_bytes)
        except Exception as e:
            raise SendMessageError(f'Erreur lors de l\'envoi du message: {e}')

    def purge_queue(self, queue_name):
        try:
            self.channel.queue_purge(queue=queue_name)
        except Exception as e:
            print(f'Erreur lors de la purge de la queue {queue_name}: {e}')

    def consume_input_queue(self):
        while True:
            method_frame, header_frame, body = self.channel.basic_get(queue=QUEUE_INPUT, auto_ack=True)
            if method_frame:
                message = json.loads(body)
                socket_id = message.get('socket_id')
                access_token = message.get('access_token')
                question = message.get('question')
                print(f"Consuming message: {message}")

                if socket_id and access_token and question:
                    # Simulate processing the question and generating an answer
                    answer = f"Processed answer for the question: {question}"
                    status = random.choice(['SUCCESS', 'REFUSED', 'ERROR'])
                    response = {
                        'status': status,
                        'answer': answer,
                        'socket_id': socket_id
                    }
                    self.send_to_queue(response, QUEUE_OUTPUT)
                else:
                    print(f"Invalid message format: {message}")
            else:
                break

    def consume_output_queue(self):
        messages = []
        while True:
            method_frame, header_frame, body = self.channel.basic_get(queue=QUEUE_OUTPUT, auto_ack=True)
            if method_frame:
                message = json.loads(body)
                messages.append(message)
            else:
                break
        return messages


    def dispose(self):
        print('Fermeture de la connexion à RabbitMQ')
        close_rabbitmq_handle(self.channel, self.connection)
