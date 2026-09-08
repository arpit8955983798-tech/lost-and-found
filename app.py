from flask import Flask, render_template, request, session, redirect, url_for, send_from_directory, send_file
from flask_sqlalchemy import SQLAlchemy
import os
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from difflib import SequenceMatcher
from datetime import datetime

app = Flask(__name__)
print("STATIC FOLDER:", app.static_folder)
app.secret_key = "lost-found-secret-key"
# Database configuration
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///lostfound.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route("/muj-logo")
def muj_logo():
    logo_path = os.path.join(
        app.static_folder,
        "images",
        "logo.jpg",
        "muj_logo.jpg"
    )
    return send_file(logo_path)

# TF-IDF Similarity Function
def field_similarity(value1, value2):
   value1 = (value1 or "").lower().strip()
   value2 = (value2 or "").lower().strip()

   if not value1 or not value2:
        return 0

   if value1 == value2:
        return 100

   return SequenceMatcher(None, value1, value2).ratio() * 100


def calculate_similarity(item1, item2):

    name_score = field_similarity(
        item1.item_name,
        item2.item_name
    )

    category_score = field_similarity(
        item1.category,
        item2.category
    )

    colour_score = field_similarity(
        item1.colour,
        item2.colour
    )

    brand_score = field_similarity(
        item1.brand,
        item2.brand
    )

    description_score = field_similarity(
        item1.description,
        item2.description
    )

    total_score = (
    name_score * 0.40 +
    category_score * 0.20 +
    colour_score * 0.15 +
    brand_score * 0.20 +
    description_score * 0.05
)

    return round(total_score, 2)

# Lost Item Table
class LostItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String(300), nullable=True)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    lost_date = db.Column(db.String(20))
    lost_location = db.Column(db.String(150))
    contact = db.Column(db.String(100))
    colour = db.Column(db.String(50))
    brand = db.Column(db.String(100))
    lost_time = db.Column(db.String(20))


# Found Item Table
class FoundItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    image = db.Column(db.String(300), nullable=True)
    item_name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    found_date = db.Column(db.String(20))
    found_location = db.Column(db.String(150))
    contact = db.Column(db.String(100))
    colour = db.Column(db.String(50))
    brand = db.Column(db.String(100))
    found_time = db.Column(db.String(20))
    
    # User Table
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    password = db.Column(db.String(200), nullable=False)

    # Notification Table
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

    message = db.Column(
        db.String(500),
        nullable=False
    )

    is_read = db.Column(
        db.Boolean,
        default=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    # Feedback Table
class Feedback(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False)

@app.route("/feedback", methods=["GET", "POST"])
def feedback():
    if request.method == "POST":
        message = request.form["message"]
        rating = request.form["rating"]

        feedback = Feedback(
            user_id=session.get("user_id"),
            message=message,
            rating=rating
        )

        db.session.add(feedback)
        db.session.commit()

        return render_template("feedback.html", success="Feedback submitted successfully!")

    return render_template("feedback.html")
@app.route("/owner-feedback")
def owner_feedback():

    feedbacks = Feedback.query.order_by(Feedback.id.desc()).all()

    return render_template(
        "owner_feedback.html",
        feedbacks=feedbacks
    )
@app.route("/report-lost", methods=["GET", "POST"])
def report_lost():
    matches = []
    print("REPORT LOST ROUTE OPENED")

    if request.method == "POST":

        image_file = request.files.get("image")
        image_filename = None

        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_filename
                )
            )

        item = LostItem(
            user_id=session.get("user_id"),
            image=image_filename,
            item_name=request.form["item_name"],
            category=request.form["category"],
            description=request.form["description"],
            lost_date=request.form["lost_date"],
            lost_location=request.form["lost_location"],
            contact=request.form["contact"],
            colour=request.form["colour"],
            brand=request.form["brand"],
            lost_time=request.form["lost_time"]
        )

        db.session.add(item)
        db.session.commit()

        # Find similar found items
        found_items = FoundItem.query.all()
        matches = []

        for found in found_items:
            score = calculate_similarity(item, found)

            if score >= 30:
                matches.append({
                    "item": found,
                    "score": score
                })
                # Keep only the most probable match
    if matches:
        matches = [max(matches, key=lambda x: x["score"])]

        print("Similar found items:", matches)

        # Create notifications
        for match in matches:
            found_item = match["item"]

            if found_item.user_id:
                notification = Notification(
                    user_id=found_item.user_id,
                    message=f"A possible match was found for your lost item: {item.item_name}"
                )
                db.session.add(notification)

        db.session.commit()
    return render_template(
    "report_lost.html",
    matches=matches
)

    return render_template("report_lost.html")

def field_similarity(value1, value2):
    value1 = (value1 or "").lower().strip()
    value2 = (value2 or "").lower().strip()

    if not value1 or not value2:
        return 0

    if value1 == value2:
        return 100

    return SequenceMatcher(None, value1, value2).ratio() * 100


def calculate_similarity(item, found):
    name_score = field_similarity(
        item.item_name,
        found.item_name
    )

    brand_score = field_similarity(
        item.brand,
        found.brand
    )

    colour_score = field_similarity(
        item.colour,
        found.colour
    )

    category_score = field_similarity(
        item.category,
        found.category
    )

    description_score = field_similarity(
        item.description,
        found.description
    )

    score = (
        name_score * 0.35 +
        brand_score * 0.20 +
        colour_score * 0.15 +
        category_score * 0.15 +
        description_score * 0.15
    )

    return round(score, 2)

def find_matches(item, opposite_items):
    matches = []

    for opposite in opposite_items:
        score = calculate_similarity(item, opposite)
        

        if score >= 20:
            matches.append({
                "item": opposite,
                "score": score
            })

    matches.sort(key=lambda x: x["score"], reverse=True)

    return matches

@app.route("/search")
def search():
    query = request.args.get("query", "")

    lost_items = LostItem.query.filter(
        LostItem.item_name.ilike(f"%{query}%")
    ).all()

    found_items = FoundItem.query.filter(
        FoundItem.item_name.ilike(f"%{query}%")
    ).all()

    return render_template(
        "search.html",
        lost_items=lost_items,
        found_items=found_items,
        query=query
    )
@app.route("/report-found", methods=["GET", "POST"])
def report_found():
    if request.method == "POST":
        image_file = request.files.get("image")
        image_filename = None

        if image_file and image_file.filename:
            image_filename = secure_filename(image_file.filename)
            image_file.save(os.path.join(app.config["UPLOAD_FOLDER"], image_filename))

        item = FoundItem(
            user_id=session.get("user_id"),
            image=image_filename,
            item_name=request.form["item_name"],
            category=request.form["category"],
            description=request.form["description"],
            found_date=request.form["found_date"],
            found_location=request.form["found_location"],
            contact=request.form["contact"],
          colour=request.form["colour"],
          brand=request.form["brand"],
        found_time=request.form["found_time"]
)
        db.session.add(item)
        db.session.commit()

        return render_template("report_success.html")

    return render_template("report_found.html")
@app.route("/found-items")
def found_items():
    items = FoundItem.query.all()
    return render_template("found_items.html", items=items)
@app.route("/lost-items")
def lost_items():
    items = LostItem.query.all()
    return render_template("lost_items.html", items=items)
@app.route("/about")
def about():
    return render_template("about.html")
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]

        user = User(
            username=username,
            email=email,
            password=password
        )

        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = User.query.filter_by(
            email=email,
            password=password
        ).first()

        if user:
         session["user_id"] = user.id
         session["username"] = user.username
         return render_template("index.html")
        else:
         return render_template("login.html", error="Invalid email or password")

    return render_template("login.html")
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))
@app.route("/notifications")
def notifications():
    user_id = session.get("user_id")

    if not user_id:
        return redirect(url_for("login"))

    notifications = Notification.query.filter_by(
        user_id=user_id
    ).order_by(
        Notification.created_at.desc()
    ).all()

    return render_template(
       "notification.html",
        notifications=notifications
    )
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/test-ml")
def test_ml():
    text1 = "black iPhone 13 found near library"
    text2 = "black iPhone 13 lost near college library"

    score = calculate_similarity(text1, text2)

    return f"TF-IDF Similarity: {score}%"


with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)