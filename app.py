from flask import Flask, session, request, jsonify
from flask_socketio import SocketIO, emit, disconnect
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import os
import ssl
from config import Config
from models import db, SessionToken
from flask_talisman import Talisman
from rabbitmq_handler import RabbitMQHandler

app = Flask(__name__)
# Configure Talisman for security headers
talisman = Talisman(
    app,
    content_security_policy={
        'default-src': [
            "'self'"
        ],
        'script-src': [
            "'self'",
            "'unsafe-inline'",
            "'unsafe-eval'"
        ]
    },
    force_https=True,
    session_cookie_secure=True,
    session_cookie_http_only=True,
    content_security_policy_nonce_in=['script-src'],
    referrer_policy='strict-origin-when-cross-origin'
)

app.config.from_object(Config)

db.init_app(app)
app.config['SESSION_SQLALCHEMY'] = db

Session(app)
socketio = SocketIO(app, cors_allowed_origins="*")
rabbitmq_handler = RabbitMQHandler(socketio)


def validate_api_key(api_key):
    valid_api_keys = ["example_valid_key"]
    return api_key in valid_api_keys


def generate_access_token():
    return os.urandom(24).hex()


def store_token_in_db(access_token):
    new_token = SessionToken(access_token=access_token)
    db.session.add(new_token)
    db.session.commit()
    return new_token.id


def delete_token_from_db(access_token):
    SessionToken.query.filter_by(access_token=access_token).delete()
    db.session.commit()


@app.route('/api/request-token', methods=['POST'])
def request_token():
    data = request.json
    api_key = data.get('API_KEY')

    if not api_key:
        return jsonify({'error': 'API_KEY is required'}), 400

    if not validate_api_key(api_key):
        return jsonify({'error': 'Invalid API_KEY'}), 401

    access_token = generate_access_token()
    token_id = store_token_in_db(access_token)
    session['access_token'] = access_token
    session['token_id'] = token_id
    return jsonify({'access_token': access_token}), 200



@socketio.on('ask')
def handle_ask(data):
    api_key = data.get('API_KEY')
    if not validate_api_key(api_key):
        emit('error', {'error': 'Invalid API_KEY'})
        return

    access_token = data.get('access_token')
    token_id = session.get('token_id')

    if not access_token or not token_id:
        access_token = generate_access_token()
        token_id = store_token_in_db(access_token)
        session['access_token'] = access_token
        session['token_id'] = token_id

    question = data.get('question')
    print(f"Received question: {question}")
    print(f"Generated access token: {access_token} with ID: {token_id}")

    # Utiliser `sid` pour obtenir l'ID de session dans le contexte SocketIO
    rabbitmq_handler.send_result({'socket_id': request.sid, 'access_token': access_token, 'question': question})
    emit('status', {'status': 'queued', 'token_id': token_id})


@socketio.on('disconnect')
def handle_disconnect():
    access_token = session.get('access_token')
    if access_token:
        delete_token_from_db(access_token)
        print(f"Deleted access token: {access_token}")


@socketio.on('disconnect')
def handle_disconnect():
    with app.app_context():
        access_token = session.get('access_token')
        if access_token:
            delete_token_from_db(access_token)
            print(f"Deleted access token: {access_token}")



def post_to_queue(question, access_token):
    print(f"Question mise en file d'attente : {question} avec le token : {access_token}")


if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    context.load_cert_chain(certfile='cert.pem', keyfile='key.pem')

    print("Starting server with HTTPS...")

    socketio.run(app, host='0.0.0.0', port=5000, ssl_context=context, allow_unsafe_werkzeug=True)
