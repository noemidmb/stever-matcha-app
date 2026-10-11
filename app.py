import os
import secrets
import smtplib
import sqlite3
import threading
from email.message import EmailMessage

from flask import Flask, render_template, g, abort, request, jsonify
app = Flask(__name__)
DATABASE = "stever.db"

# Customization choices -> extra price in cents
OPTIONS = {
    "milk": {"Whole milk": 0, "Oat milk": 75, "Almond milk": 75, "Soy milk": 50, "No milk": 0},
    "sweetness": {"Unsweetened": 0, "Lightly sweet": 0, "Regular": 0, "Extra sweet": 0},
    "temp": {"Iced": 0, "Hot": 0},
}


def get_db():
    """Open one database connection per request."""
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row  # lets us use row["name"]
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create tables, and add sample data the first time."""
    db = sqlite3.connect(DATABASE)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS popups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS menu_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price_cents INTEGER NOT NULL,
            available INTEGER NOT NULL DEFAULT 1
        );
                CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            popup_id INTEGER NOT NULL REFERENCES popups(id),
            customer_name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL REFERENCES orders(id),
            menu_item_id INTEGER NOT NULL REFERENCES menu_items(id),
            item_name TEXT NOT NULL,
            milk TEXT NOT NULL,
            sweetness TEXT NOT NULL,
            temp TEXT NOT NULL,
            unit_price_cents INTEGER NOT NULL,
            quantity INTEGER NOT NULL
        );
    """)

    if db.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0] == 0:
        db.executemany(
            "INSERT INTO menu_items (name, description, price_cents) VALUES (?, ?, ?)",
            [
                ("Classic Matcha Latte", "Ceremonial-grade matcha with your choice of milk", 600),
                ("Iced Strawberry Matcha", "Matcha over strawberry puree and milk", 700),
                ("Honey Matcha", "Lightly sweetened with local honey", 650),
                ("Straight Matcha", "Just matcha and water, whisked fresh", 500),
            ],
        )
        db.executemany(
            "INSERT INTO popups (location, date, time, notes) VALUES (?, ?, ?, ?)",
            [
                ("Annika's apartment", "2026-11-07", "2:00 PM - 5:00 PM", "Bring a friend!"),
                ("Library lawn", "2026-11-14", "12:00 PM - 3:00 PM", "Weather permitting"),
            ],
        )
    db.commit()
    db.close()

def send_email(subject, body):
    """Email a notification. Settings come from environment variables."""
    to_addr = os.environ.get("NOTIFY_EMAIL")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not (to_addr and user and password):
        print("[email not set up yet]", subject, "\n" + body)
        return
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = user
        msg["To"] = to_addr
        msg.set_content(body)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(user, password)
            server.send_message(msg)
    except Exception as e:
        print("Email failed:", e)


@app.route("/")
def index():
    popups = get_db().execute(
        "SELECT * FROM popups ORDER BY date"
    ).fetchall()
    return render_template("index.html", popups=popups)


@app.route("/menu")
def menu():
    items = get_db().execute(
        "SELECT * FROM menu_items WHERE available = 1"
    ).fetchall()
    return render_template("menu.html", items=items)

@app.route("/order/<int:popup_id>")
def order_page(popup_id):
    db = get_db()
    popup = db.execute("SELECT * FROM popups WHERE id = ?", (popup_id,)).fetchone()
    if popup is None:
        abort(404)
    items = db.execute("SELECT * FROM menu_items WHERE available = 1").fetchall()
    return render_template("order.html", popup=popup, items=items, options=OPTIONS)

@app.route("/api/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    db = get_db()

    name = str(data.get("customer_name") or "").strip()[:50]
    if not name:
        return jsonify(error="Please enter your name."), 400

    popup = db.execute("SELECT * FROM popups WHERE id = ?", (data.get("popup_id"),)).fetchone()
    if popup is None:
        return jsonify(error="That pop-up doesn't exist."), 400

    raw_items = data.get("items")
    if not isinstance(raw_items, list) or not 0 < len(raw_items) <= 30:
        return jsonify(error="Your cart is empty."), 400

    # Rebuild every line from our own database. We never trust prices from the browser.
    lines = []
    for it in raw_items:
        if not isinstance(it, dict):
            return jsonify(error="Bad item."), 400
        menu_row = db.execute(
            "SELECT * FROM menu_items WHERE id = ? AND available = 1",
            (it.get("menu_item_id"),)).fetchone()
        milk, sweet, temp = it.get("milk"), it.get("sweetness"), it.get("temp")
        try:
            qty = int(it.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 0
        if (menu_row is None or milk not in OPTIONS["milk"]
                or sweet not in OPTIONS["sweetness"]
                or temp not in OPTIONS["temp"] or not 1 <= qty <= 10):
            return jsonify(error="Something in your cart isn't valid."), 400
        unit = (menu_row["price_cents"] + OPTIONS["milk"][milk]
                + OPTIONS["sweetness"][sweet] + OPTIONS["temp"][temp])
        lines.append((menu_row["id"], menu_row["name"], milk, sweet, temp, unit, qty))

    code = secrets.token_urlsafe(5)  # random order code
    cur = db.execute(
        "INSERT INTO orders (popup_id, customer_name, code) VALUES (?, ?, ?)",
        (popup["id"], name, code))
    db.executemany(
        """INSERT INTO order_items
           (order_id, menu_item_id, item_name, milk, sweetness, temp, unit_price_cents, quantity)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [(cur.lastrowid, *line) for line in lines])
    db.commit()

    # Build the notification email and send it in the background
    total = sum(l[5] * l[6] for l in lines)
    body_lines = [f"{l[6]} x {l[1]} ({l[4]}, {l[2]}, {l[3]})" for l in lines]
    body = (f"{name} placed an order for {popup['location']}\n\n"
            + "\n".join(body_lines)
            + f"\n\nTotal: ${total / 100:.2f} (pay in person)")
    threading.Thread(target=send_email,
                     args=(f"New Stever Matcha order from {name}", body),
                     daemon=True).start()

    return jsonify(code=code), 201
    
if __name__ == "__main__":
    init_db()
    app.run(port=5001, debug=True)