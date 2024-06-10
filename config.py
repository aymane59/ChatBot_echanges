import os

class Config:
    SECRET_KEY = os.urandom(24)
    SQLALCHEMY_DATABASE_URI = 'sqlite:///sessions.db'
    SESSION_TYPE = 'sqlalchemy'
    SESSION_SQLALCHEMY = None
    SSL_CERTIFICATE = 'cert.pem'
    SSL_KEY = 'key.pem'
