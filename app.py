from flask import Flask, render_template, request, redirect, session, jsonify
from pymongo import MongoClient
import os
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import requests



app = Flask(__name__)
app.secret_key = "super-secret-key"

# MongoDB connection
MONGO_URI = os.environ.get("MONGODB_URI")
client = MongoClient(MONGO_URI)
db = client["AIPESM"]

users = db.users
classes = db.classes
students = db.students
marks = db.marks
syllabus = db.syllabus
subjects = db.subjects


def parse_syllabus(text):
    units = []

    parts = re.split(r"(Unit\s+\d+:)", text)

    for i in range(1, len(parts), 2):
        unit_name = parts[i].replace(":", "").strip()
        content = parts[i + 1].strip()

        if content:
            units.append({
                "unit": unit_name,
                "content": content
            })

    return units

def get_weak_subjects(student_email, class_id):
    weak = []

    for m in marks.find({
        "student_email": student_email,
        "class_id": class_id
    }):
        if m["marks"] < 40:
            weak.append(m["subject"])

    return weak

def recommend_resources(subject, class_id):
    resources_col = db.resources

    # Fetch syllabus units
    syllabus_docs = syllabus.find({
        "subject": subject,
        "class_id": class_id
    })

    syllabus_text = " ".join([s["content"] for s in syllabus_docs])

    if not syllabus_text.strip():
        return []

    # Fetch resources
    resource_docs = list(resources_col.find({"subject": subject}))
    resource_texts = [r["description"] for r in resource_docs]

    # TF-IDF
    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform([syllabus_text] + resource_texts)

    similarities = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

    results = []
    for i, score in enumerate(similarities):
        r = resource_docs[i]
        r["score"] = float(score)
        results.append(r)

    # Sort by relevance
    results.sort(key=lambda x: x["score"], reverse=True)

    return results

def build_search_query(subject, class_id):
    units = syllabus.find({
        "subject": subject,
        "class_id": class_id
    })

    text = " ".join([u["content"] for u in units])

    keywords = text.replace(",", " ").replace(".", " ")

    return f"{subject} {keywords} syllabus notes tutorial pdf"

def filter_results(results):
    blacklist = ["from scratch", "build your own", "make an os", "osdev"]

    filtered = []
    for r in results:
        text = (r["title"] + " " + r["snippet"]).lower()
        if not any(bad in text for bad in blacklist):
            filtered.append(r)

    return filtered


def serpapi_search(query):
    api_key = os.environ.get("SERPAPI_KEY")

    params = {
        "engine": "google",
        "q": query,
        "num": 10,
        "api_key": api_key
    }

    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()

    results = []
    for r in data.get("organic_results", []):
        results.append({
            "title": r.get("title"),
            "snippet": r.get("snippet", ""),
            "link": r.get("link")
        })

    return results

def rank_search_results(syllabus_text, search_results):
    docs = [syllabus_text] + [r["snippet"] for r in search_results]

    vectorizer = TfidfVectorizer()
    vectors = vectorizer.fit_transform(docs)

    scores = cosine_similarity(vectors[0:1], vectors[1:]).flatten()

    ranked = []
    for i, score in enumerate(scores):
        item = search_results[i]
        item["score"] = float(score)
        ranked.append(item)

    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked


# ---------------- ROUTES ----------------

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        user = users.find_one({"email": email})

        print("EMAIL:", email)
        print("PASSWORD (RAW):", password)
        print("USER FROM DB:", user)

        if user and check_password_hash(user["password"], password):
            session["role"] = user["role"]
            session["email"] = user["email"]


            if user["role"] == "teacher":
                return redirect("/teacher")
            else:
                return redirect("/student")

        return "Invalid login"

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/teacher")
def teacher():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    teacher_email = session["email"]

    teacher_classes = list(classes.find(
        {"teacher_email": teacher_email},
        {"name": 1}
    ))

    return render_template("teacher.html", classes=teacher_classes)

from collections import defaultdict

@app.route("/class/<class_id>")
def class_details(class_id):
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    class_id = ObjectId(class_id)

    class_obj = classes.find_one({"_id": class_id})
    class_students = list(students.find({"class_id": class_id}))
    class_subjects = list(subjects.find({"class_id": class_id}))

    # -------- NEW: aggregate average marks per subject --------
    subject_totals = defaultdict(int)
    subject_counts = defaultdict(int)

    class_marks = marks.find({"class_id": class_id})

    for m in class_marks:
        subject_totals[m["subject"]] += m["marks"]
        subject_counts[m["subject"]] += 1

    subject_averages = {
        sub: round(subject_totals[sub] / subject_counts[sub], 2)
        for sub in subject_totals
    }
    # ---------------------------------------------------------

    return render_template(
        "class.html",
        class_obj=class_obj,
        students=class_students,
        subjects=class_subjects,
        subject_averages=subject_averages  # 👈 pass to template
    )



@app.route("/student-profile/<email>")
def student_profile(email):
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    student = students.find_one({"email": email})
    student_marks = list(marks.find({"student_email": email}))

    return render_template(
        "student_profile.html",
        student=student,
        marks=student_marks
    )

@app.route("/update-mark", methods=["POST"])
def update_mark():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    student_email = request.form["student_email"]
    subject = request.form["subject"]
    marks_value = int(request.form["marks"])

    student = students.find_one({"email": student_email})
    class_id = student["class_id"]

    marks.update_one(
        {
            "student_email": student_email,
            "class_id": class_id,
            "subject": subject
        },
        {"$set": {"marks": marks_value}},
        upsert=True
    )

    return redirect(f"/student-profile/{student_email}")

@app.route("/add-subject", methods=["POST"])
def add_subject():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    class_id = ObjectId(request.form["class_id"])
    subject = request.form["subject"]

    # Save subject
    subjects.insert_one({
        "class_id": class_id,
        "subject": subject
    })

    # Apply subject to ALL students with marks = 0
    class_students = students.find({"class_id": class_id})

    for s in class_students:
        marks.update_one(
            {
                "student_email": s["email"],
                "class_id": class_id,
                "subject": subject
            },
            {"$set": {"marks": 0}},
            upsert=True
        )

    return redirect(f"/class/{class_id}")


@app.route("/add-marks", methods=["POST"])
def add_marks():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    student_email = request.form["student_email"]
    class_id = ObjectId(request.form["class_id"])
    subject = request.form["subject"]
    marks_value = int(request.form["marks"])

    marks.update_one(
        {
            "student_email": student_email,
            "class_id": class_id,
            "subject": subject
        },
        {
            "$set": {
                "marks": marks_value
            }
        },
        upsert=True
    )

    return redirect("/teacher")


@app.route("/create-class", methods=["POST"])
def create_class():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    class_name = request.form["class_name"]
    teacher_email = "teacher@mail.com"  # for now (we'll make this dynamic later)

    classes.insert_one({
        "name": class_name,
        "teacher_email": teacher_email
    })

    return redirect("/teacher")

@app.route("/add-student", methods=["POST"])
def add_student():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    class_id = ObjectId(request.form["class_id"])
    email = request.form["student_email"]
    name = request.form["student_name"]

    # Add student academic record
    students.insert_one({
        "email": email,
        "name": name,
        "class_id": class_id
    })

    # Create login account if not exists
    if not users.find_one({"email": email}):
        users.insert_one({
            "email": email,
            "password": generate_password_hash("student123"),
            "role": "student"
        })

    # Apply existing subjects with default marks
    class_subjects = subjects.find({"class_id": class_id})
    for sub in class_subjects:
        marks.update_one(
            {
                "student_email": email,
                "class_id": class_id,
                "subject": sub["subject"]
            },
            {"$set": {"marks": 0}},
            upsert=True
        )

    return redirect(f"/class/{class_id}")


@app.route("/delete-student", methods=["POST"])
def delete_student():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    email = request.form["student_email"]
    class_id = ObjectId(request.form["class_id"])

    students.delete_one({"email": email, "class_id": class_id})
    marks.delete_many({"student_email": email, "class_id": class_id})

    return redirect(f"/class/{class_id}")

@app.route("/delete-subject", methods=["POST"])
def delete_subject():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    subject = request.form["subject"]
    class_id = ObjectId(request.form["class_id"])

    subjects.delete_one({
        "subject": subject,
        "class_id": class_id
    })

    marks.delete_many({
        "subject": subject,
        "class_id": class_id
    })

    return redirect(f"/class/{class_id}")

@app.route("/delete-class", methods=["POST"])
def delete_class():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    class_id = ObjectId(request.form["class_id"])

    classes.delete_one({"_id": class_id})
    students.delete_many({"class_id": class_id})
    subjects.delete_many({"class_id": class_id})
    marks.delete_many({"class_id": class_id})

    return redirect("/teacher")


@app.route("/student")
def student():
    if session.get("role") != "student":
        return "Unauthorized", 403

    email = session["email"]

    student_entry = students.find_one({"email": email})
    if not student_entry:
        return "Student not assigned to a class"

    class_id = student_entry["class_id"]

    student_marks = []
    for m in marks.find({"student_email": email, "class_id": class_id}):
        student_marks.append({
            "subject": m["subject"],
            "marks": m["marks"]
        })

    weak_subjects = get_weak_subjects(email, class_id)

    ai_results = {}

    for subject in weak_subjects:
        query = build_search_query(subject, class_id)
        search_results = serpapi_search(query)

        syllabus_docs = syllabus.find({
            "subject": subject,
            "class_id": class_id
        })
        syllabus_text = " ".join([s["content"] for s in syllabus_docs])

        ranked = rank_search_results(syllabus_text, search_results)
        ranked = filter_results(ranked)

        ai_results[subject] = ranked[:5]
        chart_subjects = [m["subject"] for m in student_marks]
        chart_marks = [m["marks"] for m in student_marks]


    return render_template(
        "student.html",
        marks=student_marks,
        weak_subjects=weak_subjects,
        recommendations=ai_results,
        chart_subjects=chart_subjects,
        chart_marks=chart_marks
    )

@app.route("/upload-syllabus", methods=["POST"])
def upload_syllabus():
    if session.get("role") != "teacher":
        return "Unauthorized", 403

    subject = request.form["subject"]
    class_id = ObjectId(request.form["class_id"])
    raw_text = request.form["syllabus_text"]

    units = parse_syllabus(raw_text)

    # Remove old syllabus for this subject + class
    syllabus.delete_many({
        "class_id": class_id,
        "subject": subject
    })

    # Insert new units
    for u in units:
        syllabus.insert_one({
            "class_id": class_id,
            "subject": subject,
            "unit": u["unit"],
            "content": u["content"]
        })

    return redirect("/teacher")


@app.route("/health")
def health():
    try:
        db.command("ping")
        return jsonify({
            "status": "OK",
            "database": "connected"
        })
    except Exception as e:
        return jsonify({
            "status": "ERROR",
            "message": str(e)
        }), 500


# TEMP: one-time seed route
@app.route("/seed")
def seed():
    users.delete_many({})

    users.insert_many([
        {
            "email": "teacher@mail.com",
            "password": generate_password_hash("teacher123"),
            "role": "teacher"
        },
        {
            "email": "student@mail.com",
            "password": generate_password_hash("student123"),
            "role": "student"
        }
    ])

    return "Users created"

@app.route("/seed-resources")
def seed_resources():
    resources = db.resources
    resources.delete_many({})

    resources.insert_many([
        {
            "subject": "Operating Systems",
            "type": "text",
            "title": "CPU Scheduling Notes",
            "description": "process scheduling, round robin, priority scheduling",
            "link": "https://www.geeksforgeeks.org/cpu-scheduling/"
        },
        {
            "subject": "Operating Systems",
            "type": "video",
            "title": "Gate Smashers OS Playlist",
            "description": "operating systems, scheduling, deadlocks, memory management",
            "link": "https://www.youtube.com/"
        }
    ])

    return "Resources seeded"


@app.route("/debug-users")
def debug_users():
    return {
        "count": users.count_documents({}),
        "users": list(users.find({}, {"email": 1, "_id": 0}))
    }

@app.route("/debug-classes")
def debug_classes():
    return {
        "count": classes.count_documents({}),
        "classes": list(classes.find({}, {"name": 1, "_id": 0}))
    }

@app.route("/debug-students")
def debug_students():
    data = []
    for s in students.find():
        data.append({
            "email": s["email"],
            "class_id": str(s["class_id"])
        })

    return {
        "count": len(data),
        "students": data
    }

@app.route("/debug-marks")
def debug_marks():
    data = []
    for m in marks.find():
        data.append({
            "student_email": m["student_email"],
            "class_id": str(m["class_id"]),
            "subject": m["subject"],
            "marks": m["marks"]
        })

    return {
        "count": len(data),
        "marks": data
    }

@app.route("/debug-syllabus")
def debug_syllabus():
    data = []
    for s in syllabus.find():
        data.append({
            "subject": s["subject"],
            "unit": s["unit"],
            "content": s["content"],
            "class_id": str(s["class_id"])
        })

    return {
        "count": len(data),
        "syllabus": data
    }


if __name__ == "__main__":
    app.run()
