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
    connection = pika.BlockingConnection(pika.ConnectionParameters(RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue="book_updates")

    def callback(ch, method, properties, body):
        msg = json.loads(body)
        data = msg["data"]
        book = Book.query.get(data["id"])
        if not book:
            book = Book(**data)
            db.session.add(book)
        else:
            for k, v in data.items():
                setattr(book, k, v)
        db.session.commit()
        print(f"[SYNC] Catálogo actualizado: {data['title']}")

    channel.basic_consume(queue="book_updates", on_message_callback=callback, auto_ack=True)
    print("📡 Esperando eventos de RabbitMQ...")
    channel.start_consuming()

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
