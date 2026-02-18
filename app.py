from flask import Flask, render_template, request, redirect, session, jsonify
import os
import psycopg2
from urllib.parse import urlparse


app = Flask(__name__)
app.secret_key = "fitguide_secret"

@app.route("/")
def home():
    return redirect("/login")


# ---------------- DATABASE (MySQL) ----------------

DATABASE_URL = os.environ.get("DATABASE_URL")

url = urlparse(DATABASE_URL)

db = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port
)
# Create users table if not exists
with db.cursor() as cursor:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100),
            email VARCHAR(100) UNIQUE,
            password VARCHAR(200)
        );
    """)
    db.commit()





# ---------------- REGISTER ----------------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        cursor = db.cursor()
        cursor.execute(
            "INSERT INTO users (name, email, password) VALUES (%s, %s, %s)",
            (name, email, password)
        )
        db.commit()
        return redirect("/login")

    return render_template("register.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor = db.cursor(dictionary=True)
        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session["user_id"] = user["user_id"]

            if user["onboarding_done"] == 0:
                return redirect("/onboarding")

            return redirect("/dashboard")

        return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")



# ---------------- CALORIE + MACRO FUNCTIONS ----------------
def calculate_calories(weight, height, age, gender, goal):
    if gender.lower() == "male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    if "fat" in goal.lower() or "loss" in goal.lower():
        return int(bmr - 500)
    elif "gain" in goal.lower():
        return int(bmr + 500)
    else:
        return int(bmr + 200)


def calculate_macros(calories, weight, goal):
    if "gain" in goal.lower():
        protein_grams = weight * 2.2
    else:
        protein_grams = weight * 2.0

    protein_calories = protein_grams * 4
    fat_calories = calories * 0.25
    fat_grams = fat_calories / 9
    carb_calories = calories - (protein_calories + fat_calories)
    carb_grams = carb_calories / 4

    return {
        "protein": int(protein_grams),
        "carbs": int(carb_grams),
        "fat": int(fat_grams)
    }



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

        cursor = db.cursor()
        cursor.execute("""
            UPDATE users
            SET age=%s, gender=%s, height=%s, weight=%s,
                body_type=%s, goal=%s, level=%s,
                onboarding_done=1
            WHERE user_id=%s
        """, (age, gender, height, weight, body_type, goal, level, session["user_id"]))
        db.commit()

        return redirect("/dashboard")

    return render_template("onboarding.html")



# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)

    # ✅ Get user profile data
    cursor.execute("""
        SELECT age, gender, height, weight, body_type, goal, level
        FROM users
        WHERE user_id = %s
    """, (session["user_id"],))
    user = cursor.fetchone()

    # Get muscle groups
    cursor.execute("SELECT id, name FROM muscle_groups")
    muscle_groups = cursor.fetchall()

    cursor.execute("SELECT id, muscle_group_id, name FROM sub_muscles")
    sub_muscles = cursor.fetchall()

    return render_template(
        "dashboard.html",
        user=user,
        muscle_groups=muscle_groups,
        sub_muscles=sub_muscles
    )




# ---------------- EXERCISE PLAN ----------------
@app.route("/exercise-plan", methods=["POST"])
def exercise_plan():
    if "user_id" not in session:
        return redirect("/login")

    muscle_group_id = request.form.get("muscle_group")
    sub_muscle_id = request.form.get("sub_muscle")

    cursor = db.cursor(dictionary=True)

    cursor.execute("SELECT name FROM muscle_groups WHERE id=%s", (muscle_group_id,))
    mg = cursor.fetchone()

    cursor.execute("SELECT name FROM sub_muscles WHERE id=%s", (sub_muscle_id,))
    sm = cursor.fetchone()

    if not mg or not sm:
        return render_template("exercise_plan.html", exercises=[], message="Invalid selection")

    muscle_group = mg["name"]
    sub_muscle = sm["name"]

    cursor.execute("SELECT body_type, goal, level FROM users WHERE user_id=%s", (session["user_id"],))
    user = cursor.fetchone()

    cursor.execute("""
    SELECT exercise_name, primary_muscle, secondary_muscle, video_embed_url
    FROM exercises
    WHERE LOWER(muscle_group) = LOWER(%s)
    AND LOWER(sub_muscle) = LOWER(%s)
""", (
    muscle_group.strip(),
    sub_muscle.strip()
))


    exercises = cursor.fetchall()

    return render_template("exercise_plan.html",
                           exercises=exercises,
                           message="Exercises loaded successfully")



# ---------------- DIET PLAN ----------------
@app.route("/diet-plan")
def diet_plan():
    if "user_id" not in session:
        return redirect("/login")

    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT age, gender, height, weight, body_type, goal, level
        FROM users WHERE user_id=%s
    """, (session["user_id"],))

    user = cursor.fetchone()

    calories = calculate_calories(user["weight"], user["height"], user["age"], user["gender"], user["goal"])
    macros = calculate_macros(calories, user["weight"], user["goal"])

    diet_plan = {
        "Breakfast": [
            {"name": "Oats + Milk + Banana", "cal": 350, "protein": 12, "carbs": 60, "fat": 5, "type": "veg"},
            {"name": "Egg Omelette", "cal": 200, "protein": 18, "carbs": 3, "fat": 14, "type": "nonveg"},
            {"name": "Paneer Sandwich", "cal": 300, "protein": 18, "carbs": 28, "fat": 10, "type": "veg"},
        ],

        "Lunch": [
            {"name": "Rice + Dal + Vegetables", "cal": 500, "protein": 18, "carbs": 80, "fat": 10, "type": "veg"},
            {"name": "Chicken Breast + Salad", "cal": 450, "protein": 35, "carbs": 20, "fat": 12, "type": "nonveg"},
            {"name": "Paneer + Salad", "cal": 420, "protein": 28, "carbs": 18, "fat": 15, "type": "veg"},
        ],

        "Dinner": [
            {"name": "Chapati + Sabji + Salad", "cal": 400, "protein": 12, "carbs": 60, "fat": 8, "type": "veg"},
            {"name": "Egg Omelette + Veggies", "cal": 350, "protein": 20, "carbs": 10, "fat": 15, "type": "nonveg"},
            {"name": "Vegetable Soup + Paneer", "cal": 300, "protein": 18, "carbs": 12, "fat": 8, "type": "veg"},
        ]
    }

    return render_template("diet_plan.html",
                           diet_plan=diet_plan,
                           calories=calories,
                           macros=macros,
                           goal=user["goal"],
                           body_type=user["body_type"])


# ---------------- SUB MUSCLE ----------------
@app.route("/get-sub-muscles/<int:group_id>")
def get_sub_muscles(group_id):
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT id, name FROM sub_muscles WHERE muscle_group_id=%s", (group_id,))
    return jsonify(cursor.fetchall())


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------------- RUN ----------------

import os

port = int(os.environ.get("PORT", 5000))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=port)

