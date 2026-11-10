import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import abort

app = Flask(__name__)

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', "development-key-change-this")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATABASE = os.path.join(BASE_DIR, "pivet.db")

print("DATABASE LOCATION:", DATABASE)
print("DATABASE EXISTS:", os.path.exists(DATABASE))


def get_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def init_db():
    db = get_db()

    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (opportunity_id) REFERENCES opportunities(id)
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
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    db.commit()
    db.close()


    ADMIN_USERNAME = os.environ.get(
            "ADMIN_USERNAME",
            "admin"
    )

    ADMIN_PASSWORD = os.environ.get(
            "ADMIN_PASSWORD",
            "Peanut"
    )

def admin_required(view):

    @wraps(view)
    def wrapped_view(*args, **kwargs):

        if not session.get("is_admin"):

            flash(
                "Administrator login required.",
                "warning"
            )

            return redirect(
                url_for("admin_login")
            )

        return view(*args, **kwargs)

    return wrapped_view

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        )

        password = request.form.get(
            "password",
            ""
        )

        if(
            username == ADMIN_USERNAME
            and password == ADMIN_PASSWORD
        ):

            session.clear()

            session["is_admin"] = True

            flash(
                "Administrator login successful.",
                "success"
            )

            return redirect(
                url_for("admin_dashboard")
            )

        flash(
            "Invalid administrator credentials.",
            "danger"
        )

        return redirect(
            url_for("admin_login")
        )

    return render_template(
        "admin_login.html",
    )

@app.route("/admin_dashboard")
@admin_required
def admin_dashboard():

    db = get_db()

    try:

        users = db.execute(
            """
            SELECT *
            FROM users
            ORDER BY id DESC
            """
        ).fetchall()

        entries = db.execute(
            """
            SELECT
                hours.*,
                users.name AS volunteer_name
                users.email
                
            FROM hours
            
            JOIN users
            ON hours.user_id = users.id
            
            ORDER BY id DESC
            """
        ).fetchall()

        stats = {

            "volunteers": db.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0],

            "pending": db.execute(
                """
                FROM hours
                WHERE approved = 0
                """
            ).fetchone()[0],

            "approved_hours": db.execute(
                """
                SELECT COALESCE(SUM(duration), 0)
                FROM hours
                WHERE approved = 1
                """
            ).fetchone()[0]


        }

    finally:

        db.close()

    return render_template(
        "admin_dashboard.html",

        users=users,

        entries=entries,

        stats=stats
    )

@app.route(
    "/admin/approve/<int:hour_id>",
    methods=["POST"]
)
@admin_required
def approve_hour(hour_id):

    db = get_db()

    try:

        result = db.execute(
            """
            UPDATE hours
            SET approved = 1
            WHERE id = ?
            """,

            (hour_id,)
        )

        db.commit()

        if result.rowcount == 0:

            flash(
                "Hour entry not found.",
                "danger"
            )

        else:

            flash(
                "Volunteer hours approved.",
                "success"
            )

    finally:

        db.close()

    return redirect(
        url_for("admin_dashboard")
    )

@app.route("/admin/logout")
@admin_required
def admin_logout():

    session.clear()

    flash(
        "Admin logged out.",
        "success"
    )

    return redirect(
        url_for("home")
    )

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

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
          "success"
    )

    return redirect(url_for("home"))

@app.route("/opportunities")
def opportunities():

    db = get_db()

    try:

        items = db.execute(
            """
            SELECT *
            FROM opportunities
            ORDER BY id DESC
            """
        ).fetchall()

        signed_up = []

        if "user_id" in session:

            signups = db.execute(
                """
                SELECT opportunity_id
                FROM signups
                WHERE user_id = ?
                """,

                (session["user_id"],)
            ).fetchall()

            signed_up = [
                row["opportunity_id"]
                for row in signups
            ]

    finally:

        db.close()

    return render_template(
        "opportunities.html",
        opportunities=items,
        signed_up=signed_up
    )

@app.route("/join/<int:opportunity_id>", methods=["POST"])
@login_required
def join_opportunity(opportunity_id):

    db = get_db()

    opportunity = db.execute(
        "SELECT * FROM opportunities WHERE id = ?",
        (opportunity_id,)
    ).fetchone()

    if not opportunity:
        db.close()
        flash("Opportunity not found.")
        return redirect(url_for("opportunities"))

    try:
        db.execute(
            """
            INSERT INTO signups (user_id, opportunity_id)
            VALUES (?, ?)
            """,
            (session["user_id"], opportunity_id)
        )

        db.commit()
        flash("You successfully signed up!")

    except sqlite3.IntegrityError:
        flash("You have already signed up for this opportunity.")

    finally:
        db.close()

    return redirect(url_for("opportunities"))

@app.route("/hours", methods=["GET", "POST"])
@login_required
def hours():

    db = get_db()

    try:

        if request.method == "POST":

            activity = request.form.get(
                "activity",
                ""
            ).strip()

            volunteer_date = request.form.get(
                "volunteer_date",
                ""
            )

            duration = request.form.get(
                "duration",
                ""
            )

            duration = request.form.get(
                "notes",
                ""
            ).strip()

            if not activity or not volunteer_date:

                flash(
                    "Please complete the required fields.",
                    "danger"
                )

                return redirect(url_for("hours"))

            try:

                duration = float(duration)

            except ValueError:

                flash(
                    "Please enter a valid number of hours.",
                    "danger"
                )

                return redirect(url_for("hours"))

            if duration <= 0 or duration > 24:

                flash(
                    "Hours must be between 0 and 24.",
                    "danger"
                )

                return redirect(url_for("hours"))

            db.execute(
                """
                INSERT INTO hours (
                    user_id,
                    activity,
                    volunteer_date,
                    duration,
                    notes
                ) VALUES (?, ?, ?, ?, ?)
                """,

                (
                    session["user_id"],
                    activity,
                    volunteer_date,
                    duration,
                    notes
                )
            )

            db.commit()

            flash(
                "Your hours were submitted for approval.",
                "success"
            )

            return redirect(url_for("hours"))

        entries = db.execute(
            """
            SELECT *
            FROM hours
            WHERE user_id = ?
            ORDER BY id DESC
            """,

            (session["user_id"],)
        ).fetchall()

        total_hours = db.execute(
            """
            SELECT COALESCE(SUM(duration), 0)
            FROM hours
            WHERE user_id = ?
            AND approved = 1
            """,

            (session["user_id"],)
        ).fetchone()[0]

    finally:

        db.close()

    return render_template(
        "hours.html",

        entries=entries,

        total_hours=round(total_hours, 1)
    )

@app.route("/dashboard")
@login_required
def dashboard():

    db = get_db()

    try:

        user = db.execute(
            """
            SELECT *
            FROM users
            WHERE id = ?
            """,

            (session["user_id"],)
        ).fetchone()

        entries = db.execute(
            """
            SELECT *
            FROM hours
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT 5
            """,

            (session["user_id"],)
        ).fetchall()

        joined = db.execute(
            """
            SELECT opportunities.*
            FROM opportunities
            
            JOIN signups
            ON opportunities.id = signups.opportunity_id
            
            WHERE signups.user_id = ?
            
            ORDER BY signups.id DESC
            """,

            (session["user_id"],)
        ).fetchall()

        total_hours = db.execute(
            """
            SELECT COALESCE(SUM(duration), 0)
            FROM hours
            WHERE user_id = ?
            AND approved = 1
            """,

            (session["user_id"],)
        ).fetchone()[0]

    finally:

        db.close()

    return render_template(
        "dashboard.html",

        user=user,

        entries=entries,

        joined=joined,

        total_hours=round(total_hours, 1)
    )

@app.route("/chat", methods=["POST"])
def chat():

    data = request.get_json(silent=True) or {}

    message = data.get(
        "message",
        ""
    ).strip().lower()

    if not message:

        return jsonify({
            "reply": "Please enter a message.",
        }), 400

    if "opportunity" in message:

        reply = (
            "You can explore volunteer opportunities "
            "on our Opportunities page."
        )

    elif "hours" in message:

        reply = (
            "You can track your volunteer hours "
            "on the Track Hours page."
        )

    elif "register" in message or "account" in message:

        reply = (
            "You can create an account using "
            "our registration page."
        )

    elif "login" in message:

        reply = (
            "You can log in using the Login page."
        )

    elif "help" in message:

        reply = (
            "I can help you find opportunities, "
            "track hours, or create an account."
        )

    else:

        reply = (
            "Thanks for your message! You can explore "
            "volunteer opportunities or track your hours "
            "on Pivet."
        )

    return jsonify({
        "reply": reply
    })

def seed_opportunities():

    db = get_db()

    try:

        count = db.execute(
            "SELECT COUNT(*) FROM opportunities"
        ).fetchone()[0]

        if count == 0:

            opportunities = [

                (
                    "Community Garden Volunteer",

                     "Help plant vegetables, maintain garden beds, and support local food access.",

                    "Portland, Oregon",

                    "2026-11-15",

                    "Community Green Initiative"
                ),

                (
                    "Food Bank Assistant",

                    "Help organize food donations and prepare food packages for families.",

                    "Hillsboro, Oregon",

                    "2026-11-20",

                    "Local Food Bank"
                ),

                (
                    "Neighborhood Cleanup",

                    "Join a community cleanup event and help make local parks cleaner.",

                    "Beaverton, Oregon",

                    "2026-11-22",

                    "Community Action Group"
                )

            ]

            db.executemany(
                """
                INSERT INTO opportunities (
                    title,
                    description,
                    location,
                    date,
                    organization
                )
                VALUES (?, ?, ?, ?, ?)
                """,

                opportunities
            )

            db.commit()

    finally:

         db.close()

@app.errorhandler(404)
def page_not_found(error):

    return render_template("404.html"), 404

if __name__ == "__main__":

    init_db()

    seed_opportunities()

    app.run(
        debug=True
    )