from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app_db):
    global db
    db = app_db

class Book(db.Model):
    __tablename__ = 'book'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150))
    author = db.Column(db.String(100))
    description = db.Column(db.Text)
    price = db.Column(db.Float)
    stock = db.Column(db.Integer)
    seller_id = db.Column(db.Integer)
