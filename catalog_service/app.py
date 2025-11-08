import pika, json, threading, os
from models import db
from models.book import Book
from flask import Flask, jsonify
from flasgger import Swagger
from models import db
from models.book import Book

DB_URI = os.environ.get("DATABASE_URI", "mysql+pymysql://user:password@db_catalog/bookstore_catalog")

app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "Catalog Service API",
        "description": "Endpoint para ver todos los libros disponibles",
        "version": "1.0.0"
    }
})

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:password@db_catalog/bookstore_catalog"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

db.init_app(app)

with app.app_context():
    db.create_all()

def consume_book_updates():
    import time
    with app.app_context():

        # ============================
        # Intentar conexión hasta lograrlo
        # ============================
        while True:
            try:
                print(f"[Catalog Service] Intentando conectar a RabbitMQ en {RABBITMQ_HOST}...")
                connection = pika.BlockingConnection(
                    pika.ConnectionParameters(host=RABBITMQ_HOST)
                )
                print("[Catalog Service] ✅ Conectado a RabbitMQ")
                break
            except pika.exceptions.AMQPConnectionError:
                print("[Catalog Service] ❌ RabbitMQ no disponible, reintentando en 3s...")
                time.sleep(3)

        # ============================
        # Configurar canal y cola
        # ============================
        channel = connection.channel()
        channel.queue_declare(queue="book_updates")

        print("📡 [Catalog Service] Esperando eventos de RabbitMQ...")

        # ============================
        # Callback de consumo
        # ============================
        def callback(ch, method, properties, body):
            print(f"[Catalog Service] 🔔 Mensaje recibido: {body}")

            msg = json.loads(body)
            data = msg["data"]

            # Crear o actualizar libro
            book = Book.query.get(data["id"])
            if not book:
                book = Book(**data)
                db.session.add(book)
                action = "CREATED"
            else:
                for k, v in data.items():
                    setattr(book, k, v)
                action = "UPDATED"

            db.session.commit()
            print(f"[Catalog Service] ✅ Libro {action}: {data['title']}")

        # ============================
        # Iniciar consumo
        # ============================
        channel.basic_consume(
            queue="book_updates",
            on_message_callback=callback,
            auto_ack=True
        )

        try:
            channel.start_consuming()
        except Exception as e:
            print(f"[Catalog Service] ❌ Error durante el consumo: {e}")


# Lanza el consumidor en un hilo paralelo
threading.Thread(target=consume_book_updates, daemon=True).start()

@app.route("/", methods=["GET"])
def home():
    return jsonify({"service": "catalog", "status": "running"})

@app.route("/books", methods=["GET"])
def get_books():
    """
    Obtener todos los libros del catálogo
    ---
    tags:
      - Catálogo
    responses:
      200:
        description: Lista de libros disponibles
        schema:
          type: array
          items:
            type: object
            properties:
              id: {type: integer}
              title: {type: string}
              author: {type: string}
              description: {type: string}
              price: {type: number}
              stock: {type: integer}
    """
    books = Book.query.all()
    result = []
    for b in books:
        result.append({
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "description": b.description,
            "price": b.price,
            "stock": b.stock
        })
    return jsonify(result)



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
