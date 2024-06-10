from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class SessionToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    access_token = db.Column(db.String(256), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
