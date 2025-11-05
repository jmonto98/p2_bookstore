from models import db

class DeliveryAssignment(db.Model):
    __tablename__ = "delivery_assignment"
    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchase.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('delivery_provider.id'))
    status = db.Column(db.String(50), default="Pending")
    purchase = db.relationship("Purchase", backref=db.backref("delivery", lazy=True))
    provider = db.relationship("DeliveryProvider", backref=db.backref("assignments", lazy=True))
