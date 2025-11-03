import os
import requests
from flask import Flask, request, jsonify
from flasgger import Swagger
from models import db, Purchase

DB_URI = os.environ.get("DATABASE_URI", "mysql+pymysql://user:password@db/bookstore")
AUTH_URL = os.environ.get("AUTH_URL", "http://auth_service:5001")

app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "Order Service API",
        "description": "Endpoint para la compra de libros",
        "version": "1.0.0"
    }
})

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:password@db/bookstore"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()

@app.route("/", methods=["GET"])
def home():
    return jsonify({"service": "order", "status": "running"})

@app.route("/order", methods=["POST"])
def create_order():
    """
    Crear una nueva orden de compra
    ---
    tags:
      - Órdenes
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
            - book_id
          properties:
            email: {type: string}
            password: {type: string}
            book_id: {type: integer}
            quantity: {type: integer}
    responses:
      201:
        description: Orden creada exitosamente
      401:
        description: Usuario no autorizado
      400:
        description: Stock insuficiente o datos inválidos
    """
    data = request.json
    # Se requiere email y password para validar usuario (simple en local)
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "email y password requeridos para validar usuario"}), 400

    # validar usuario contra auth_service
    try:
        resp = requests.post(AUTH_URL + "/validate", json={"email": email, "password": password}, timeout=5)
    except Exception as e:
        return jsonify({"error": "no se pudo conectar con auth_service", "detail": str(e)}), 503
    if resp.status_code != 200:
        return jsonify({"error": "usuario no validado"}), 401

    book_id = data.get("book_id")
    qty = int(data.get("quantity", 1))

    book = Book.query.get(book_id)
    if not book:
        return jsonify({"error": "libro no existe"}), 404
    if book.stock < qty:
        return jsonify({"error": "stock insuficiente"}), 400

    total = book.price * qty
    # crear compra
    purchase = Purchase(user_email=email, book_id=book_id, quantity=qty, total_price=total, status="Pending Payment")
    book.stock = book.stock - qty
    db.session.add(purchase)
    db.session.commit()

    return jsonify({"message": "orden creada", "order": {"id": purchase.id, "total": total}}), 201

@app.route("/orders", methods=["GET"])
def list_orders():
    """
    Obtener todas las órdenes de compra
    ---
    tags:
      - Órdenes
    responses:
      200:
        description: Lista de órdenes
    """
    orders = Purchase.query.all()
    result = []
    for o in orders:
        result.append({
            "id": o.id,
            "user_email": o.user_email,
            "book_id": o.book_id,
            "quantity": o.quantity,
            "total_price": o.total_price,
            "status": o.status
        })
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)
