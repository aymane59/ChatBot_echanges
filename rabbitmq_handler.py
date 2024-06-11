import threading
import pika
import json
import random
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


def process_question(rabbitmq_handler, question_data):
    # Simuler le traitement de l'IA
    status = random.choice(['SUCCESS', 'REFUSED', 'ERROR'])
    question = question_data.get('question')
    socket_id = question_data.get('socket_id')

    # Créer la réponse
    response = {
        'status': status,
        'answer': f"Answer to '{question}'",
        'socket_id': socket_id
    }

    # Envoyer la réponse dans la queue de sortie
    rabbitmq_handler.send_result(response)

    return response


def callback(rabbitmq_handler, ch, method, properties, body):
    try:
        json_body = json.loads(body)
        print(f" [x] Received {json_body}")
        process_question(rabbitmq_handler, json_body)
    except Exception as e:
        print('Erreur lors de la réception du message:', str(e))


def output_consumer(rabbitmq_handler):
    channel2, connection2 = get_rabbitmq_handle(connection_string=CONNEXION_URI)
    channel2.basic_consume(queue=QUEUE_OUTPUT, auto_ack=True,
                           on_message_callback=lambda ch, method, properties, body: callback_output(rabbitmq_handler, ch, method, properties, body))
    print('Waiting for responses...')
    channel2.start_consuming()


def callback_output(rabbitmq_handler, ch, method, properties, body):
    try:
        json_body = json.loads(body)
        print(f" [x] Processed response {json_body}")
        rabbitmq_handler.send_to_client(json_body)
        return json_body
    except Exception as e:
        print('Erreur lors de la réception du message:', str(e))


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
            self.purge_queues()
        except Exception as e:
            print('Erreur lors de l\'initialisation de la queue de messages:', str(e))
            exit(1)

        try:
            self.consumer_thread = threading.Thread(target=output_consumer, args=(self,))
            self.consumer_thread.start()
        except Exception as e:
            print('Erreur lors de la création du thread de consommation:', str(e))
            exit(1)

    def purge_queues(self):
        try:
            self.channel.queue_purge(queue=QUEUE_INPUT)
            self.channel.queue_purge(queue=QUEUE_OUTPUT)
            print('Queues purged successfully')
        except Exception as e:
            print('Erreur lors de la purge des queues:', str(e))

    def send_result(self, body: dict):
        try:
            body_bytes = json.dumps(body, default=str).encode('utf-8')
            self.channel.basic_publish(exchange='',
                                       routing_key=QUEUE_OUTPUT,
                                       body=body_bytes)
            print(f" [x] Sent response {body}")
        except Exception as e:
            raise SendMessageError(f'Erreur lors de l\'envoi du message: {e}')

    def send_to_queue(self, queue, body: dict):
        try:
            body_bytes = json.dumps(body, default=str).encode('utf-8')
            self.channel.basic_publish(exchange='',
                                       routing_key=queue,
                                       body=body_bytes)
            print(f" [x] Sent to {queue} {body}")
        except Exception as e:
            raise SendMessageError(f'Erreur lors de l\'envoi du message dans la queue {queue}: {e}')

    def send_to_client(self, body: dict):
        try:
            socket_id = body['socket_id']
            self.socketio.emit('response', body, room=socket_id)
            print(f" [x] Sent to client {body}")
        except Exception as e:
            print('Erreur lors de l\'envoi au client:', str(e))

    def process_queue(self):
        responses = []
        while True:
            method_frame, header_frame, body = self.channel.basic_get(queue=QUEUE_INPUT)
            if method_frame:
                self.channel.basic_ack(method_frame.delivery_tag)
                response = process_question(self, json.loads(body))
                responses.append(response)
                sleep(2)  # Attente artificielle pour simuler le traitement
            else:
                break
        return responses

    def process_responses(self):
        responses = []
        while True:
            method_frame, header_frame, body = self.channel.basic_get(queue=QUEUE_OUTPUT)
            if method_frame:
                self.channel.basic_ack(method_frame.delivery_tag)
                response = callback_output(self, None, method_frame, header_frame, body)
                responses.append(response)
            else:
                break
        return responses
