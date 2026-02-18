import os
from flask import Flask, render_template, request, redirect, session
import psycopg2

app = Flask(__name__)
app.secret_key = "supersecretkey"

# -----------------------------
# DATABASE CONNECTION (Render)
# -----------------------------
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True


# -----------------------------
# CREATE TABLE (AUTO)
# -----------------------------
def create_table():
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(100)
        );
    """)
    cursor.close()

create_table()


# -----------------------------
# HOME
# -----------------------------
@app.route("/")
def home():
    return render_template("login.html")


# -----------------------------
# REGISTER
# -----------------------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
                (name, email, password)
            )
            conn.commit()
            return redirect("/login")
        except:
            return "User already exists!"
        finally:
            cursor.close()

    return render_template("register.html")


# -----------------------------
# LOGIN
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, password FROM users WHERE email = %s",
            (email,)
        )
        user = cursor.fetchone()
        cursor.close()

        if user and user[1] == password:
            session["user_id"] = user[0]
            return redirect("/dashboard")
        else:
            return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")


# -----------------------------
# DASHBOARD
# -----------------------------
@app.route("/dashboard")
def dashboard():
    if "user_id" in session:
        return render_template("dashboard.html")
    return redirect("/login")


# -----------------------------
# LOGOUT
# -----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# -----------------------------
# RUN
# -----------------------------
if __name__ == "__main__":
    app.run()
