import os
from flask import Flask, jsonify
from flasgger import Swagger
from models.book import db, Book

DB_URI = os.environ.get("DATABASE_URI", "mysql+pymysql://user:password@db/bookstore")

app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "Catalog Service API",
        "description": "Endpoint para ver todos los libros disponibles",
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
