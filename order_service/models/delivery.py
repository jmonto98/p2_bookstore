from models import db

class DeliveryProvider(db.Model):
    __tablename__ = "delivery_provider"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    contact = db.Column(db.String(100))