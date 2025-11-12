import pika, json, os
import requests
from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
from flasgger import Swagger
from models import db
from models.book import Book
from models.purchase import Purchase
from models.payment import Payment
from models.delivery import DeliveryProvider
from models.delivery_assignment import DeliveryAssignment

# ------------------------------------------------------
# Configuración base
# ------------------------------------------------------
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

swagger = Swagger(app, template={
    "info": {
        "title": "Purchase Service API",
        "description": "Microservicio de gestión de compras, pagos y entregas",
        "version": "2.0.0"
    }
})


app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:password@db-main/bookstore_main"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
AUTH_URL = "http://auth-service:5001/validate"
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

db.init_app(app)

with app.app_context():
    db.create_all()
    

def notify_catalog(event_type, payload):
    """Envía eventos al catálogo a través de RabbitMQ."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue="book_updates")
    message = {"event": event_type, "data": payload}
    channel.basic_publish(exchange="", routing_key="book_updates", body=json.dumps(message))
    connection.close()

# ------------------------------------------------------
# Helper: Validación de token JWT
# ------------------------------------------------------
def validate_jwt(request):
    """Valida el token JWT contra el microservicio de autenticación."""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return None, {"error": "token no proporcionado"}, 401
    token = auth_header.split(" ")[1]
    try:
        resp = requests.post(AUTH_URL, json={"token": token}, timeout=5)
        if resp.status_code != 200:
            return None, {"error": "token inválido o expirado"}, 401
        return resp.json()["user"], None, 200
    except Exception as e:
        return None, {"error": f"Error al validar token: {str(e)}"}, 503

# ------------------------------------------------------
# Estado del servicio
# ------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """Estado del servicio"""
    return jsonify({"service": "purchase", "status": "running"})

# ======================================================
# ===================== LIBROS ==========================
# ======================================================
@app.route("/books", methods=["GET"])
def list_books():
    """
    Obtener todos los libros
    ---
    tags:
      - Libros
    responses:
      200:
        description: Lista de libros
    """
    books = Book.query.all()
    return jsonify([
        {"id": b.id, "title": b.title, "author": b.author,
         "description": b.description, "price": b.price,
         "stock": b.stock} for b in books
    ])

@app.route("/books/<int:id>", methods=["GET"])
def get_book(id):
    """
    Obtener un libro por ID
    ---
    tags:
      - Libros
    parameters:
      - in: path
        name: id
        required: true
        type: integer
    responses:
      200:
        description: Libro encontrado
      404:
        description: No encontrado
    """
    book = Book.query.get(id)
    if not book:
        return jsonify({"error": "libro no encontrado"}), 404
    return jsonify({
        "id": book.id, "title": book.title, "author": book.author,
        "description": book.description, "price": book.price,
        "stock": book.stock
    })

@app.route("/books", methods=["POST"])
def add_book():
    """
    Agregar un nuevo libro
    ---
    tags:
      - Libros
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [title, author, price]
          properties:
            title: {type: string}
            author: {type: string}
            description: {type: string}
            price: {type: number}
            stock: {type: integer}
    responses:
      201:
        description: Libro agregado
    """
    data = request.json
    book = Book(**data)
    db.session.add(book)
    db.session.commit()

    notify_catalog("book_created", {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "description": book.description,
        "price": book.price,
        "stock": book.stock
    })

    return jsonify({"message": "Libro agregado", "book_id": book.id}), 201

@app.route("/books/<int:id>", methods=["PUT"])
def update_book(id):
    """
    Actualizar un libro existente
    ---
    tags:
      - Libros
    parameters:
      - in: path
        name: id
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            title: {type: string}
            author: {type: string}
            description: {type: string}
            price: {type: number}
            stock: {type: integer}
    responses:
      200:
        description: Libro actualizado
      404:
        description: No encontrado
    """
    book = Book.query.get(id)
    if not book:
        return jsonify({"error": "libro no encontrado"}), 404
    for key, value in request.json.items():
        setattr(book, key, value)
    db.session.commit()
    
    notify_catalog("book_updated", {
        "id": book.id,
        "title": book.title,
        "author": book.author,
        "description": book.description,
        "price": book.price,
        "stock": book.stock      
    })
    
    return jsonify({"message": "Libro actualizado"})

@app.route("/books/<int:id>", methods=["DELETE"])
def delete_book(id):
    """
    Eliminar un libro
    ---
    tags:
      - Libros
    parameters:
      - in: path
        name: id
        required: true
        type: integer
    responses:
      200:
        description: Libro eliminado
    """
    book = Book.query.get(id)
    if not book:
        return jsonify({"error": "libro no encontrado"}), 404
    db.session.delete(book)
    db.session.commit()
    
    notify_catalog("book_deleted", {
    "id": book.id
    })
    
    return jsonify({"message": "Libro eliminado"})

# ======================================================
# ==================== COMPRAS =========================
# ======================================================
@app.route("/purchase", methods=["POST"])
def make_purchase():
    """
    Crear una compra
    ---
    tags:
      - Compras
    parameters:
      - in: header
        name: Authorization
        description: Token JWT del usuario
        required: true
        type: string
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - book_id
            - quantity
          properties:
            book_id:
              type: integer
            quantity:
              type: integer
    responses:
      201:
        description: Compra creada correctamente
      400:
        description: Datos inválidos o stock insuficiente
      401:
        description: Token inválido o usuario no autorizado
    """

    data = request.json

    if not data or "book_id" not in data or "quantity" not in data:
        return jsonify({"error": "book_id y quantity son requeridos"}), 400

    book_id = data["book_id"]
    quantity = data["quantity"]

    # ========= VALIDAR TOKEN CON AUTH_SERVICE ==========
    token = request.headers.get("Authorization")

    if not token:
        return jsonify({"error": "Token requerido"}), 401

    validate_resp = requests.post(
        f"{AUTH_URL}",
        json={"token": token}
    )

    if validate_resp.status_code != 200:
        return jsonify({"error": "Token inválido"}), 401

    validate_json = validate_resp.json()
    user_id = validate_json["user"]["id"]

    # ========== CONSULTAR LIBRO ========================
    book = Book.query.get(book_id)

    if not book:
        return jsonify({"error": "Libro no encontrado"}), 404

    if book.stock < quantity:
        return jsonify({
            "error": "No hay suficiente stock disponible",
            "stock_actual": book.stock
        }), 400

    # ========== CALCULAR TOTAL =========================
    total_price = book.price * quantity

    # ========== CREAR PURCHASE =========================
    new_purchase = Purchase(
        user_id=user_id,
        book_id=book_id,
        quantity=quantity,
        total_price=total_price,
        status="Pending Payment"
    )

    # ========== ACTUALIZAR STOCK =======================
    book.stock -= quantity

    db.session.add(new_purchase)
    db.session.commit()

    notify_catalog("book_updated", {
    "id": book.id,
    "stock": book.stock      
    })

    return jsonify({
        "message": "Compra creada",
        "purchase_id": new_purchase.id,
        "total_price": total_price,
        "remaining_stock": book.stock
    }), 201

@app.route("/purchases", methods=["GET"])
def list_purchases():
    """
    Listar todas las compras
    ---
    tags:
      - Compras
    responses:
      200:
        description: Lista de compras
    """
    purchases = Purchase.query.all()
    return jsonify([
        {"id": p.id, "user_id": p.user_id, "book_id": p.book_id,
         "book_name": Book.query.get(p.book_id).title if Book.query.get(p.book_id) else "",
         "quantity": p.quantity, "total_price": p.total_price,
         "status": p.status} for p in purchases
    ])

@app.route("/purchase/<int:id>", methods=["PUT"])
def update_purchase(id):
    """
    Actualizar estado de una compra
    ---
    tags:
      - Compras
    parameters:
      - in: path
        name: id
        required: true
        type: integer
      - in: body
        name: body
        schema:
          type: object
          properties:
            status: {type: string}
    responses:
      200:
        description: Compra actualizada
    """
    purchase = Purchase.query.get(id)
    if not purchase:
        return jsonify({"error": "Compra no encontrada"}), 404
    purchase.status = request.json.get("status", purchase.status)
    db.session.commit()
    return jsonify({"message": "Compra actualizada"})

@app.route("/purchase/<int:id>", methods=["DELETE"])
def delete_purchase(id):
    """
    Eliminar una compra
    ---
    tags:
      - Compras
    parameters:
      - in: path
        name: id
        required: true
        type: integer
    responses:
      200:
        description: Compra eliminada
    """
    purchase = Purchase.query.get(id)
    if not purchase:
        return jsonify({"error": "Compra no encontrada"}), 404
    db.session.delete(purchase)
    db.session.commit()
    return jsonify({"message": "Compra eliminada"})

# ======================================================
# ===================== PAGOS ==========================
# ======================================================
@app.route("/payment", methods=["POST"])
def create_payment():
    """
    Registrar un pago
    ---
    tags:
      - Pagos
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [purchase_id, amount, method]
          properties:
            purchase_id: {type: integer}
            amount: {type: number}
            payment_method: {type: string}
    responses:
      201:
        description: Pago registrado correctamente
    """
    data = request.json
    payment = Payment(
        purchase_id=data["purchase_id"],
        amount=data["amount"],
        payment_method=data["payment_method"],
        payment_status="Completed"
    )
    db.session.add(payment)
    db.session.commit()

    purchase = Purchase.query.get(data["purchase_id"])
    if purchase:
        purchase.status = "Paid"
        db.session.commit()

    return jsonify({"message": "Pago registrado", "payment_id": payment.id}), 201

@app.route("/payments", methods=["GET"])
def list_payments():
    """
    Listar todos los pagos
    ---
    tags:
      - Pagos
    responses:
      200:
        description: Lista de pagos
    """
    payments = Payment.query.all()
    return jsonify([
        {"id": p.id, "purchase_id": p.purchase_id, "amount": p.amount,
         "method": p.payment_method, "status": p.payment_status} for p in payments
    ])

# ======================================================
# =================== ENTREGAS =========================
# ======================================================
@app.route("/providers", methods=["POST"])
def add_provider():
    """
    Registrar proveedor de entrega
    ---
    tags:
      - Entregas
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [name, contact]
          properties:
            name: {type: string}
            contact: {type: string}
    responses:
      201:
        description: Proveedor agregado
    """
    data = request.json
    provider = DeliveryProvider(name=data["name"], contact=data["contact"])
    db.session.add(provider)
    db.session.commit()
    return jsonify({"message": "Proveedor agregado", "provider_id": provider.id}), 201

@app.route("/providers", methods=["GET"])
def list_providers():
    """
    Listar proveedores de entrega
    ---
    tags:
      - Entregas
    responses:
      200:
        description: Lista de proveedores
    """
    providers = DeliveryProvider.query.all()
    return jsonify([
        {"id": p.id, "name": p.name, "contact": p.contact} for p in providers
    ])

@app.route("/assignments", methods=["POST"])
def create_assignment():
    """
    Asignar entrega a proveedor
    ---
    tags:
      - Entregas
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [purchase_id, provider_id]
          properties:
            purchase_id: {type: integer}
            provider_id: {type: integer}
    responses:
      201:
        description: Entrega asignada
    """
    data = request.json
    assignment = DeliveryAssignment(
        purchase_id=data["purchase_id"],
        provider_id=data["provider_id"],
        status="Assigned"
    )
    db.session.add(assignment)
    db.session.commit()

    purchase = Purchase.query.get(data["purchase_id"])
    if purchase:
        purchase.status = "On Delivery"
        db.session.commit()

    return jsonify({"message": "Entrega asignada", "assignment_id": assignment.id}), 201

@app.route("/assignments", methods=["GET"])
def list_assignments():
    """
    Listar entregas asignadas
    ---
    tags:
      - Entregas
    responses:
      200:
        description: Lista de asignaciones
    """
    assignments = DeliveryAssignment.query.all()
    return jsonify([
        {"id": a.id, "purchase_id": a.purchase_id,
         "provider_id": a.provider_id, "status": a.status} for a in assignments
    ])

# ------------------------------------------------------
# Ejecución
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5003)