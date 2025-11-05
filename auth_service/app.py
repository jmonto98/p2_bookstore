import os
import datetime
import jwt
from flask import Flask, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flasgger import Swagger
from models import db
from models.user import User

# ------------------------------------------------------
#  Configuración base de la aplicación
# ------------------------------------------------------
app = Flask(__name__)

swagger = Swagger(app, template={
    "info": {
        "title": "Auth Service API",
        "description": "Microservicio de autenticación con JWT",
        "version": "2.0.0"
    }
})

app.config["SQLALCHEMY_DATABASE_URI"] = "mysql+pymysql://user:password@db/bookstore"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "supersecretkey")

db.init_app(app)

with app.app_context():
    db.create_all()

# ------------------------------------------------------
#  Almacenamiento temporal de tokens invalidados (logout)
# ------------------------------------------------------
blacklist = set()

# ------------------------------------------------------
#  Funciones auxiliares
# ------------------------------------------------------
def create_token(user):
    """Generar un token JWT con expiración"""
    payload = {
        "user_id": user.id,
        "email": user.email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=4)
    }
    token = jwt.encode(payload, app.config["SECRET_KEY"], algorithm="HS256")
    return token


def decode_token(token):
    """Decodificar y validar un token JWT"""
    try:
        if token in blacklist:
            return None, "Token invalidado"
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token expirado"
    except jwt.InvalidTokenError:
        return None, "Token inválido"


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
    Iniciar sesión y obtener JWT
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

    token = create_token(user)
    return jsonify({"message": "login exitoso", "token": token}), 200


@app.route("/validate", methods=["POST"])
def validate_token():
    """
    Validar token JWT
    ---
    tags:
      - Autenticación
    parameters:
      - in: body
        name: body
        required: true
        description: Token JWT a validar
        schema:
          type: object
          properties:
            token:
              type: string
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    responses:
      200:
        description: Usuario válido
      401:
        description: Credenciales incorrectas
    """
    data = request.json
    token = data.get("token")
    if not token:
        return jsonify({"error": "token requerido"}), 400

    payload, error = decode_token(token)
    if error:
        return jsonify({"valid": False, "error": error}), 401

    return jsonify({"valid": True, "user": {"id": payload["user_id"], "email": payload["email"]}}), 200


@app.route("/logout", methods=["POST"])
def logout_user():
    """
    Invalidar token JWT (logout)
    ---
    tags:
      - Autenticación
    parameters:
      - in: body
        name: body
        required: true
        description: Token JWT a invalidar
        schema:
          type: object
          properties:
            token:
              type: string
              example: "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    responses:
      200:
        description: Logout exitoso, token invalidado
        schema:
          type: object
          properties:
            message:
              type: string
              example: "logout exitoso"
      400:
        description: Token no proporcionado
        schema:
          type: object
          properties:
            error:
              type: string
              example: "token requerido"
    """
    data = request.json
    token = data.get("token")
    if not token:
        return jsonify({"error": "token requerido"}), 400

    # Agregar token a la blacklist
    blacklist.add(token)
    return jsonify({"message": "logout exitoso"}), 200


# ------------------------------------------------------
#  Punto de entrada principal
# ------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
