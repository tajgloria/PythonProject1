import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import abort

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "development-key-change-this")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "nonprofithub.db")

def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db

def init_db():
    db = get_db()

    try:

        db.executescript("""
                         
            CREATE TABLE IF NOT EXISTS users (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              name TEXT NOT NULL,
              email TEXT UNIQUE NOT NULL,
              password_hash TEXT NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                         
            );
            
            CREATE TABLE IF NOT EXISTS opportunities (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              location TEXT NOT NULL,
              date TEXT NOT NULL,
              organization TEXT NOT NULL
            
            );
            
            CREATE TABLE IF NOT EXISTS signups (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              opportunity_id INTEGER NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              UNIQUE(user_id, opportunity_id),
              FOREIGN KEY (user_id) 
                REFERENCES users (id)
              FOREIGN KEY (opportunity_id)
                REFERENCES opportunities (id) 
                
            );
            
            CREATE TABLE IF NOT EXISTS hours (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER NOT NULL,
              activity TEXT NOT NULL,
              volunteer_date TEXT NOT NULL,
              duration REAL NOT NULL,
              notes TEXT,
              approved INTEGER DEFAULT 0,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              FOREIGN KEY(user_id) 
                  REFERENCES users (id)
                  
            );
            
        """)

        db.commit()

    finally:
        db.close()


@app.route("/")
def home():
    db = get_db()

    try:
        volunteer_count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]

        opportunity_count = db.execute("SELECT COUNT(*) FROM opportunities").fetchone()[0]

        total_hours = db.execute(
            """
            SELECT COALESCE(SUM(duration), 0)
            FROM hours
            WHERE approved = 1
            """
        ).fetchone()[0]

        opportunities = db.execute(
            """
            SELECT *
            FROM opportunities
            ORDER BY id DESC
            LIMIT 3
            """
        ).fetchall()

    finally:

        db.close()

    return render_template(
        "home.html",

        volunteer_count=volunteer_count,

        oppurtunity_count=opportunity_count,

        total_hours=round(total_hours, 1),

        opportunities=opportunities

    )

def login_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if "user_id" not in session:

            flash(
                "Please login first",
                "warning"
            )

            return redirect(url_for("login"))

        return view(*args, **kwargs)

    return wrapped_view

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name").strip()

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get("password", "")

        if not name or not email or not password:

            flash(
                "Please complete all required fields.",
                "danger"
            )

            return redirect(url_for("register"))

        if len(name) > 100 or len(email) > 254:

            flash(
                "Your name or email is too long.",
                "danger"
            )

            return redirect(url_for("register"))

        if len(password) < 8:

            flash(
                "Your password must be at least 8 characters long.",
                "danger"
            )

            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        db = get_db()

        try:

            db.execute(
                """
                INSERT INTO users (
                    name,
                    email, 
                    password_hash
                )
                VALUES (?, ?, ?)
                """,

                (
                    name,
                    email,
                    password_hash
                )
            )

            db.commit()

        except sqlite3.IntegrityError:

            flash(
                "An account with this email already exists.",
                "danger"
            )

            return redirect(url_for("register"))

        finally:

            db.close()

        flash(
            "Account created successfully! Please login.",
            "success"
        )

        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email",
            ""
        ).strip().lower()

        password = request.form.get(
            "password",
            ""
        )

        db = get_db()

        try:

            user = db.execute(
                """
                SELECT *
                FROM users 
                WHERE email = ?
                """,

                (email,)
            ).fetchone()

        finally:

            db.close()

        if user is None:

            flash(
                "Invalid email or password.",
                "danger"
            )

            return redirect(url_for("login"))

        if not check_password_hash(
                user["password_hash"],
                password
        ):

            flash(
                "Invalid email or password.",
                "danger"
            )

            return redirect(url_for("login"))

        session["user_id"] = user["id"]

        session["user_name"] = user["name"]

        flash(
            "You are logged in!",
            "success"
        )

        return redirect(url_for("dashboard"))

    return render_template("login.html")