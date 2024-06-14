import random
import threading
import pika
import json
from time import sleep
import requests

from exceptions import *

QUEUE_INPUT = 'queue_input'
QUEUE_OUTPUT = 'queue_output'
CONNEXION_URI = 'localhost'


def update_message_counter(access_token):
    """
    appel de l'endpoint secret qui remet le nbr de message d'un client dans la queue à 0
    :param access_token:
    :return:
    """
    response = requests.post(
        f"http://127.0.0.1:8000/api/local/7e467523-1ef8-4aee-b01f-0cdddc638e80",
        headers={'Content-Type': 'application/json'},
        data=json.dumps({"access_token": access_token}),
        verify=False
    )
    if response.status_code != 200:
        raise Exception


def get_rabbitmq_handle(connection_string, max_retries=3):
    """
    methode qui sert à initier la connection a rabbitMQ
    :param connection_string:
    :param max_retries:
    :return:
    """
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
    """
    Fermeture de la connexion à rabbitMQ
    :param channel:
    :param connection:
    :param max_retries:
    :return:
    """
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
        """
        Methode qui sert à empiler un message (question ou reponse ) dans la file donnée en paramètre
        :param body:
        :param queue_name:
        :return:
        """
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

    def consume_output_queue(self):
        def callback(ch, method, properties, body):
            """
            Methode callback qui est appelée à chaque nouvelle réponse mise par l'IA dans la queue output
            :param ch:
            :param method:
            :param properties:
            :param body:
            :return:
            """
            data = json.loads(body)
            socket_id = data.get('socket_id')
            status = data.get('status')
            answer = data.get(status)
            access_token = data.get('access_token')
            print(f"Consuming message from output queue: {data}")

            if True or (socket_id and answer and status):
                self.socketio.emit(status, {'status': status, status: answer}, room=socket_id) # envoie du mot généré par l'IA au client (status : message pour le premier mot, word pour les autres)
                if status == 'message':
                    try:
                        update_message_counter(access_token)
                    except Exception as e:
                        print(f"Error updating message counter: {e}")
            else:
                print(f"Invalid message format: {data}")

        self.channel.basic_consume(queue=QUEUE_OUTPUT, on_message_callback=callback, auto_ack=True)
        threading.Thread(target=self.channel.start_consuming).start() # On lance le Thread qui tourne en arriere plan afin de consommer le contenu de la queue

    def dispose(self):
        print('Fermeture de la connexion à RabbitMQ')
        close_rabbitmq_handle(self.channel, self.connection)
