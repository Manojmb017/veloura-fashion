import os
from datetime import datetime, timedelta, timezone
from functools import wraps

import jwt
import mysql.connector
from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()
app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173"]}})
SECRET = os.getenv("JWT_SECRET", "dev-only-change-this-secret")


def db():
    if "db" not in g:
        g.db = mysql.connector.connect(
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "fashion_store"),
        )
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    connection = g.pop("db", None)
    if connection and connection.is_connected():
        connection.close()


def token_for(user):
    return jwt.encode({"sub": user["id"], "email": user["email"], "exp": datetime.now(timezone.utc) + timedelta(hours=24)}, SECRET, algorithm="HS256")


def auth_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            return jsonify(error="Please sign in to continue."), 401
        try:
            claims = jwt.decode(header[7:], SECRET, algorithms=["HS256"])
            cursor = db().cursor(dictionary=True)
            cursor.execute("SELECT id, name, email, phone, created_at FROM users WHERE id=%s", (claims["sub"],))
            g.user = cursor.fetchone()
            cursor.close()
            if not g.user:
                return jsonify(error="Account not found."), 401
        except jwt.ExpiredSignatureError:
            return jsonify(error="Your session expired. Please sign in again."), 401
        except (jwt.InvalidTokenError, mysql.connector.Error):
            return jsonify(error="Invalid session or database unavailable."), 401
        return fn(*args, **kwargs)
    return wrapper


@app.get("/api/health")
def health():
    return jsonify(status="ok", service="FORME Fashion Store API", time=datetime.now(timezone.utc).isoformat())


@app.post("/api/auth/signup")
def signup():
    data = request.get_json(silent=True) or {}
    name, email, password = (str(data.get(k, "")).strip() for k in ("name", "email", "password"))
    if not name or not email or len(password) < 8:
        return jsonify(error="Name, email and a password of at least 8 characters are required."), 400
    try:
        cursor = db().cursor()
        cursor.execute("INSERT INTO users (name, email, password_hash) VALUES (%s,%s,%s)", (name, email.lower(), generate_password_hash(password)))
        db().commit()
        user = {"id": cursor.lastrowid, "name": name, "email": email.lower()}
        cursor.close()
        return jsonify(token=token_for(user), user=user), 201
    except mysql.connector.IntegrityError:
        return jsonify(error="An account with this email already exists."), 409
    except mysql.connector.Error:
        return jsonify(error="Could not create account. Check the database setup."), 503


@app.post("/api/auth/login")
def login():
    data = request.get_json(silent=True) or {}
    email, password = str(data.get("email", "")).strip().lower(), str(data.get("password", ""))
    try:
        cursor = db().cursor(dictionary=True)
        cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()
        cursor.close()
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify(error="Email or password is incorrect."), 401
        public_user = {"id": user["id"], "name": user["name"], "email": user["email"]}
        return jsonify(token=token_for(public_user), user=public_user)
    except mysql.connector.Error:
        return jsonify(error="Database unavailable. Check your MySQL connection."), 503


@app.get("/api/me")
@auth_required
def me():
    return jsonify(user={k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in g.user.items()})


@app.get("/api/categories")
def categories():
    return jsonify(categories=[{"name": name, "slug": name.lower()} for name in ["Men", "Women", "Kids", "Accessories", "Beauty"]])


@app.get("/api/products")
def list_products():
    category, search = request.args.get("category"), request.args.get("search", "").strip()
    query = "SELECT id, name, slug, description, category, product_type, price, compare_at_price, image_url, color, stock_quantity FROM products WHERE is_active=1"
    params = []
    if category and category.lower() != "all":
        query += " AND LOWER(category)=LOWER(%s)"; params.append(category)
    if search:
        query += " AND (name LIKE %s OR description LIKE %s OR category LIKE %s)"; term = f"%{search}%"; params.extend([term, term, term])
    query += " ORDER BY created_at DESC"
    try:
        cursor = db().cursor(dictionary=True); cursor.execute(query, tuple(params)); rows = cursor.fetchall(); cursor.close()
        for row in rows:
            if row.get("price") is not None: row["price"] = float(row["price"])
            if row.get("compare_at_price") is not None: row["compare_at_price"] = float(row["compare_at_price"])
        return jsonify(products=rows)
    except mysql.connector.Error:
        return jsonify(error="Could not load products. Check MySQL and run schema.sql."), 503


@app.get("/api/orders")
@auth_required
def orders():
    try:
        cursor = db().cursor(dictionary=True)
        cursor.execute("SELECT id, order_number, status, total_amount, created_at FROM orders WHERE user_id=%s ORDER BY created_at DESC", (g.user["id"],))
        rows = cursor.fetchall(); cursor.close()
        for row in rows:
            row["total_amount"] = float(row["total_amount"])
            row["created_at"] = row["created_at"].isoformat() if row["created_at"] else None
        return jsonify(orders=rows)
    except mysql.connector.Error:
        return jsonify(error="Could not load orders."), 503


@app.get("/api/orders/<order_number>/track")
@auth_required
def track_order(order_number):
    try:
        cursor = db().cursor(dictionary=True)
        cursor.execute("SELECT order_number, status, tracking_number, carrier, created_at, updated_at FROM orders WHERE order_number=%s AND user_id=%s", (order_number, g.user["id"]))
        order = cursor.fetchone(); cursor.close()
        if not order: return jsonify(error="Order not found."), 404
        for field in ("created_at", "updated_at"):
            if order[field]: order[field] = order[field].isoformat()
        return jsonify(order=order)
    except mysql.connector.Error:
        return jsonify(error="Could not track order."), 503


@app.errorhandler(404)
def not_found(_error): return jsonify(error="Endpoint not found."), 404


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG", "0") == "1")
