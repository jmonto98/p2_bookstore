from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def init_db(app_db):
    global db
    db = app_db

class Purchase(db.Model):
    __tablename__ = 'purchase'
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(150))
    book_id = db.Column(db.Integer)
    quantity = db.Column(db.Integer)
    total_price = db.Column(db.Float)
    status = db.Column(db.String(50))
