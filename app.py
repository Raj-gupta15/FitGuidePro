import os
import psycopg2
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "supersecret"

# ---------------- DB CONNECTION ----------------
DATABASE_URL = os.environ.get("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")

# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/login")

# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn = get_conn()
        cur = conn.cursor()

        try:
            cur.execute("""
                INSERT INTO users (name, email, password)
                VALUES (%s, %s, %s)
            """, (name, email, password))

            conn.commit()
            return redirect("/login")

        except Exception as e:
            return f"Error: {e}"

        finally:
            cur.close()
            conn.close()

    return render_template("register.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, password, onboarding_done FROM users WHERE email=%s
        """, (email,))
        user = cur.fetchone()

        cur.close()
        conn.close()

        if user and user[1] == password:
            session["user_id"] = user[0]

            if user[2] == 0:
                return redirect("/onboarding")
            return redirect("/dashboard")

        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")

# ---------------- ONBOARDING ----------------
@app.route("/onboarding", methods=["GET", "POST"])
def onboarding():
    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":
        age = request.form["age"]
        gender = request.form["gender"]
        height = request.form["height"]
        weight = request.form["weight"]
        body_type = request.form["body_type"]
        goal = request.form["goal"]
        level = request.form["level"]

        conn = get_conn()
        cur = conn.cursor()

        cur.execute("""
            UPDATE users SET 
                age=%s, gender=%s, height=%s, weight=%s,
                body_type=%s, goal=%s, level=%s,
                onboarding_done=1
            WHERE id=%s
        """, (age, gender, height, weight, body_type, goal, level, session["user_id"]))

        conn.commit()
        cur.close()
        conn.close()
        return redirect("/dashboard")

    return render_template("onboarding.html")

# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT name, age, gender, height, weight, body_type, goal, level
        FROM users WHERE id=%s
    """, (session["user_id"],))

    user = cur.fetchone()
    cur.close()
    conn.close()

    return render_template("dashboard.html", user=user)

# ---------------- GET EXERCISE PLAN ----------------
@app.route("/exercise-plan", methods=["POST"])
def exercise_plan():
    if "user_id" not in session:
        return redirect("/login")

    muscle_group = request.form.get("muscle_group")
    sub_muscle = request.form.get("sub_muscle")

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT body_type, goal, level 
        FROM users WHERE id=%s
    """, (session["user_id"],))
    user = cur.fetchone()

    cur.execute("""
        SELECT exercise_name, primary_muscle, secondary_muscle, video_embed_url
        FROM exercises
        WHERE LOWER(muscle_group)=LOWER(%s)
          AND LOWER(sub_muscle)=LOWER(%s)
          AND LOWER(body_type)=LOWER(%s)
          AND LOWER(goal)=LOWER(%s)
          AND LOWER(level)=LOWER(%s)
    """, (muscle_group, sub_muscle, user[0], user[1], user[2]))

    exercises = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("exercise_plan.html", exercises=exercises)

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)