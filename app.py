from flask import Flask, session, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
from flask_session import Session
from flask import render_template
import os
import ssl
from config import Config
from models import db, SessionToken
from flask_talisman import Talisman

from rabbitmq_handler import RabbitMQHandler
from dotenv import load_dotenv


app = Flask(__name__)

app.config.from_object(Config)

db.init_app(app)
app.config['SESSION_SQLALCHEMY'] = db

Session(app)
socketio = SocketIO(app, cors_allowed_origins="*")
rabbitmq_handler = RabbitMQHandler(socketio)

# Pour charger les variables d'environnement
load_dotenv()

API_KEY = os.environ['API_KEY']



def validate_api_key(api_key):
    """
    cette methode vérifie que l'api key fournie par le client de l'application est une clé valide
    :param api_key:
    :return:
    True / False
    """
    valid_api_keys = [API_KEY]
    return api_key in valid_api_keys


def generate_access_token():
    """
    cette methode génère un access token random pour chaque connexion
    :return:
    un access token
    """
    return os.urandom(24).hex()

# Les méthodes qui suivent servent à gérer la bdd session : enregistrer un token, detruire un token, verifier la validité d'un token...
def store_token_in_db(access_token):
    """
    cette methode enregistrer un token valide dans la db session
    :param access_token:
    :return:
    """
    new_token = SessionToken(access_token=access_token)
    db.session.add(new_token)
    db.session.commit()
    return new_token.id


def delete_token_from_db(access_token):
    """
    Cette methode sert à détruire un token de la db session
    :param access_token:
    :return:
    """
    SessionToken.query.filter_by(access_token=access_token).delete()
    db.session.commit()


def is_valid_access_token(access_token):
    """
    Cette méthode vérifie si le token fournie est un token valide c'est à dire qu'il existe dans la db session
    :param access_token:
    :return:
    """
    token = SessionToken.query.filter_by(access_token=access_token).first()
    return token is not None

def get_message_counter(access_token):
    """
    Cette méthode sert à connaître si le client ayant l'acess token donné en paramètre
    a déjà envoyé un message dans la queue (ou pas)
    :param access_token:
    :return:
    nombre de messages dans la queue pour le client
    """
    token = SessionToken.query.filter_by(access_token=access_token).first()
    if token:
        return token.compteur_messages
    else:
        return None


def update_message_counter(access_token, new_counter_value):
    """
    Cette méthode sert à mettre à jour le compteur du nombre de messages du client dans la queue
    :param access_token:
    :param new_counter_value:
    :return:
    """
    token = SessionToken.query.filter_by(access_token=access_token).first()
    if token:
        token.compteur_messages = new_counter_value
        db.session.commit()
        return True
    else:
        return False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/request_token', methods=['POST'])
def request_token():
    """
    enpoint qui sert à traiter une demande de token d'un client dans la queue input
    :return:
    """
    data = request.json
    api_key = data.get('API_KEY') # On recupère l'api key des paramètres de la requete

    if not api_key or not validate_api_key(api_key):
        return jsonify({'error': 'Invalid or missing API_KEY'}), 401

    access_token = generate_access_token() # generation d'un nouvel acess token
    token_id = store_token_in_db(access_token)  # enregistrement du token dans la db session
    session['access_token'] = access_token
    session['token_id'] = token_id

    return jsonify({'access_token': access_token}), 200


@app.route('/api/local/7e467523-1ef8-4aee-b01f-0cdddc638e80', methods=['POST'])
def update_mutex():
    # Route secrète qui sert uniquement à decrementer le nombre de messages dans la queue pour un client
    if request.remote_addr not in ('127.0.0.1', '::1'): # Interdiction de l'accès à cet endpoint
        return jsonify({'error': 'Forbiden'}), 403

    data = request.json
    access_token = data.get('access_token')

    if not access_token:
        return jsonify({'error': 'Invalid format'}), 401

    try:
        update_message_counter(access_token, 0)
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        return jsonify({'error': 'error'}), 401


@socketio.on('message')
def handle_send_message(data):
    """
    cette methode gère le comportement du middleware lorsqu'il reçoit une question du client
    :param data:
    :return:
    """
    # Recuperation de la question du clien (message), de son token ainsi que le socketID du client pour pouvoir lui transmettre la réponse plutard
    access_token = data.get('access_token')
    message = data.get('message')
    socket_id = request.sid


    if not access_token or not message:
        emit('error', {'status': 'error', 'message': 'access_token and message are required'})
        return

    compteur_messages = get_message_counter(access_token) # nbr de messages de ce même client (soit 0 ou 1 car limité)

    if compteur_messages == 0:
        if len(message) > 1000: # la longueur du message est limitée
            emit('error', {'status': 'error', 'message': 'le message est trop long'})

        if is_valid_access_token(access_token):
            print(f"Access token valid. Receiving message: {message} and sending status...")
            update_message_counter(access_token, 1) # On met a jour le nbr de messages dans la queue
            emit('loading', {'status': 'loading', 'message': message}, to=socket_id) # on indique au client que son message passera dans la queue pour attendre le traitement
            rabbitmq_handler.send_to_queue({'socket_id': socket_id, 'id': access_token, 'message': message}, 'queue_input') # on empile le message dans la queue input
        else:
            print(f"Access token invalid. message: {message} not sent.")
            emit('error', {'status': 'invalid_token', 'message': message}, to=socket_id) # erreur si le token a expiré
    else: # Cas ou ce client a deja des messages en attente de traitement, son deuxieme message ne passe meme pas dans la queue pour le traitement
        emit('error', {'status': 'error', 'message': 'Vous avez déjà un message dans la queue'})


@socketio.on('disconnect')
def handle_disconnect():
    access_token = session.get('access_token')
    if access_token:
        delete_token_from_db(access_token)
        print(f"Deleted access token: {access_token}")

def main():
    with app.app_context():
        db.create_all()

    rabbitmq_handler.consume_output_queue() # Lancement du consumer qui fait un appel callback pour traiter chaque reponse dès qu'elle arrive dans la queue output

    print("Starting server with HTTPS...")


main()
