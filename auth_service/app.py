from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger

# ------------------------------------------------------
#  Configuración base de la aplicación
# ------------------------------------------------------
app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "Auth Service API",
        "description": "Endpoints para autenticación de usuarios",
        "version": "1.0.0"
    }
})


app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:password@db/bookstore"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ------------------------------------------------------
#  Modelo de usuario
# ------------------------------------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(200))

# Crear las tablas si no existen
with app.app_context():
    db.create_all()

# ------------------------------------------------------
#  Rutas y endpoints
# ------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    """Estado del servicio"""
    return jsonify({"service": "auth", "status": "running"})


@app.route("/register", methods=["POST"])
def register_user():
    """
    Registrar un nuevo usuario
    ---
    tags:
      - Autenticación
    parameters:
      - in: body
        name: body
        description: Datos del usuario
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            name:
              type: string
            email:
              type: string
            password:
              type: string
    responses:
      201:
        description: Usuario creado correctamente
      400:
        description: Datos inválidos o usuario ya existente
    """
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email y password requeridos"}), 400

    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "usuario ya existe"}), 400

    hashed = generate_password_hash(data["password"], method="pbkdf2:sha256")
    new_user = User(name=data.get("name", ""), email=data["email"], password=hashed)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "usuario creado", "id": new_user.id}), 201


@app.route("/login", methods=["POST"])
def login_user():
    """
    Iniciar sesión
    ---
    tags:
      - Autenticación
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required:
            - email
            - password
          properties:
            email:
              type: string
            password:
              type: string
    responses:
      200:
        description: Login exitoso
      401:
        description: Credenciales inválidas
    """
    data = request.json
    if not data or not data.get("email") or not data.get("password"):
        return jsonify({"error": "email y password requeridos"}), 400

    user = User.query.filter_by(email=data["email"]).first()
    if not user or not check_password_hash(user.password, data["password"]):
        return jsonify({"error": "credenciales inválidas"}), 401

    return jsonify({
        "message": "login exitoso",
        "user": {"id": user.id, "email": user.email, "name": user.name}
    }), 200


@app.route("/validate", methods=["POST"])
def validate_user():
    """
    Validar credenciales (usado por otros microservicios)
    ---
    tags:
      - Autenticación
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          properties:
            email:
              type: string
            password:
              type: string
    responses:
      200:
        description: Usuario válido
      401:
        description: Credenciales incorrectas
    """
    data = request.json
    user = User.query.filter_by(email=data.get("email")).first()
    if user and check_password_hash(user.password, data.get("password", "")):
        return jsonify({"valid": True, "user_id": user.id}), 200
    return jsonify({"valid": False}), 401


# ------------------------------------------------------
#  Punto de entrada principal
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
