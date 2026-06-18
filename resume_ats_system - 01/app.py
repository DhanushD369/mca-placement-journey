from flask import Flask, render_template, request, redirect, session, send_file
import os
import sqlite3
import pdfplumber
import re
import io
from urllib.parse import quote
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "uploads"
DATABASE = "users.db"

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# ---------------- DATABASE ----------------
def init_db():
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT,
        password TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS resumes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        filename TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ---------------- ROLE DATABASE ----------------
ROLE_SKILLS = {
    "python_dev": {"name":"Python Developer","skills":["Python","Flask","Django","REST API"]},
    "java_dev": {"name":"Java Developer","skills":["Java","Spring Boot","Hibernate","OOP"]},
    "data_analyst": {"name":"Data Analyst","skills":["SQL","Excel","Power BI","Python"]},
    "cyber_security": {"name":"Cyber Security Analyst","skills":["Network Security","Cryptography","Ethical Hacking"]},
    "cloud_engineer": {"name":"Cloud Engineer","skills":["AWS","Azure","GCP"]},
    "devops_engineer": {"name":"DevOps Engineer","skills":["Docker","Kubernetes","AWS","CI/CD"]},
    "software_tester": {"name":"Software Tester","skills":["Manual Testing","Test Cases","Bug Tracking"]}
}

# ---------------- DIRECT COURSE LINKS ----------------
COURSE_LINKS = {
    "Python": {
        "youtube": "https://www.youtube.com/watch?v=_uQrJ0TkZlc",
        "udemy": "https://www.udemy.com/course/complete-python-bootcamp/",
        "linkedin": "https://www.linkedin.com/learning/python-essential-training-18764650"
    },
    "Flask": {
        "youtube": "https://www.youtube.com/watch?v=Z1RJmh_OqeA",
        "udemy": "https://www.udemy.com/course/python-and-flask-bootcamp-create-websites-using-flask/",
        "linkedin": "https://www.linkedin.com/learning/flask-essential-training"
    },
    "Django": {
        "youtube": "https://www.youtube.com/watch?v=F5mRW0jo-U4",
        "udemy": "https://www.udemy.com/course/python-django-the-practical-guide/",
        "linkedin": "https://www.linkedin.com/learning/django-essential-training"
    },
    "Java": {
        "youtube": "https://www.youtube.com/watch?v=eIrMbAQSU34",
        "udemy": "https://www.udemy.com/course/java-the-complete-java-developer-course/",
        "linkedin": "https://www.linkedin.com/learning/java-essential-training-2"
    },
    "SQL": {
        "youtube": "https://www.youtube.com/watch?v=HXV3zeQKqGY",
        "udemy": "https://www.udemy.com/course/the-complete-sql-bootcamp/",
        "linkedin": "https://www.linkedin.com/learning/sql-essential-training"
    },
    "Docker": {
        "youtube": "https://www.youtube.com/watch?v=fqMOX6JJhGo",
        "udemy": "https://www.udemy.com/course/docker-mastery/",
        "linkedin": "https://www.linkedin.com/learning/docker-essential-training-1"
    }
}

# ---------------- AUTH ----------------
@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        username=request.form["username"]
        password=request.form["password"]

        conn=sqlite3.connect(DATABASE)
        c=conn.cursor()
        c.execute("SELECT * FROM users WHERE username=? AND password=?",(username,password))
        user=c.fetchone()
        conn.close()

        if user:
            session["user"]=username
            return redirect("/")
        else:
            return "Invalid Login"

    return render_template("login.html")

@app.route("/signup",methods=["GET","POST"])
def signup():
    if request.method=="POST":
        username=request.form["username"]
        email=request.form["email"]
        password=request.form["password"]

        conn=sqlite3.connect(DATABASE)
        c=conn.cursor()

        # CHECK USERNAME FIRST
        c.execute("SELECT * FROM users WHERE username=?", (username,))
        existing_user = c.fetchone()

        if existing_user:
            conn.close()
            return "⚠️ Username already exists. Try another."

        # INSERT NEW USER
        c.execute("INSERT INTO users(username,email,password) VALUES(?,?,?)",
                  (username,email,password))
        conn.commit()
        conn.close()

        return redirect("/login")

    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.pop("user",None)
    return redirect("/login")

# ---------------- HOME ----------------
@app.route("/")
def index():
    if "user" not in session:
        return redirect("/login")

    return render_template("index.html",ROLE_SKILLS=ROLE_SKILLS)

# ---------------- ANALYZE ----------------
@app.route("/analyze",methods=["POST"])
def analyze():

    if "user" not in session:
        return redirect("/login")

    role_key=request.form["job_role"]
    role_data=ROLE_SKILLS[role_key]

    role_name=role_data["name"]
    required_skills=role_data["skills"]

    file=request.files["resume"]
    filepath=os.path.join(UPLOAD_FOLDER,file.filename)
    file.save(filepath)

    conn=sqlite3.connect(DATABASE)
    c=conn.cursor()
    c.execute("INSERT INTO resumes(username,filename) VALUES(?,?)",(session["user"],file.filename))
    conn.commit()
    conn.close()

    text=extract_text(filepath).lower()
    text=re.sub(r'[^a-z0-9\s-]',' ',text)

    found=[skill for skill in required_skills if skill.lower() in text]
    missing=list(set(required_skills)-set(found))

    sections={
        "Education":"education" in text,
        "Skills":"skills" in text,
        "Projects":"project" in text,
        "Experience":"experience" in text
    }

    score=int((len(found)/len(required_skills))*70 + (sum(sections.values())/4)*30)
    skill_gap=100-score

    recommendation="Highly aligned resume" if score>=75 else "Moderate alignment" if score>=50 else "Needs improvement"

    # ---------------- JOB SEARCH ----------------
    search_query = quote(role_name + " " + " ".join(found + missing[:2]))

    jobs=[
        {"title":"LinkedIn","link":f"https://www.linkedin.com/jobs/search/?keywords={search_query}"},
        {"title":"Naukri","link":f"https://www.naukri.com/{role_name.replace(' ','-')}-jobs"},
        {"title":"Infosys","link":f"https://career.infosys.com/jobs?keywords={search_query}"},
        {"title":"TCS","link":"https://www.tcs.com/careers"}
    ]

    # ---------------- DIRECT COURSE LINKS ----------------
    youtube_links={}
    udemy_links={}
    linkedin_courses={}

    for skill in missing:
        if skill in COURSE_LINKS:
            youtube_links[skill]=COURSE_LINKS[skill]["youtube"]
            udemy_links[skill]=COURSE_LINKS[skill]["udemy"]
            linkedin_courses[skill]=COURSE_LINKS[skill]["linkedin"]
        else:
            youtube_links[skill]=f"https://www.youtube.com/results?search_query={skill}"
            udemy_links[skill]=f"https://www.udemy.com/courses/search/?q={skill}"
            linkedin_courses[skill]=f"https://www.linkedin.com/learning/search?keywords={skill}"

    # STORE REPORT
    session["report_data"]={
        "score":score,
        "role":role_name,
        "found":found,
        "missing":missing,
        "jobs":jobs,
        "youtube_links":youtube_links,
        "udemy_links":udemy_links,
        "linkedin_courses":linkedin_courses
    }

    return render_template("result.html",score=score,skill_gap=skill_gap,role=role_name,
                           found=found,missing=missing,sections=sections,
                           recommendation=recommendation,jobs=jobs,
                           youtube_links=youtube_links,udemy_links=udemy_links,
                           linkedin_courses=linkedin_courses)

# ---------------- EMAIL ----------------
@app.route("/send_email")
def send_email():

    if "report_data" not in session:
        return redirect("/")

    data = session["report_data"]

    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE username=?", (session["user"],))
    result = c.fetchone()
    conn.close()

    if not result:
        return "User email not found!"

    user_email = result[0]

    # EMAIL SETUP
    sender_email = "dhanushd627@gmail.com"
    app_password = "zwsf veyn xear jset"

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = user_email
    msg["Subject"] = "AI Resume Report"

    body = f"""
Hello {session['user']},

Here is your AI Resume Report:

Role: {data['role']}
Score: {data['score']}%

Matched Skills: {', '.join(data['found'])}
Missing Skills: {', '.join(data['missing'])}

Job Links:
"""

    for job in data["jobs"]:
        body += f"{job['title']} -> {job['link']}\n"

    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, app_password)
        server.send_message(msg)
        server.quit()

        return "✅ Email Sent Successfully!"

    except Exception as e:
        return f"❌ Error sending email: {str(e)}"

# ---------------- PDF ----------------
@app.route('/download_report')
def download_report():

    data=session.get("report_data")
    if not data:
        return redirect("/")

    buffer=io.BytesIO()
    doc=SimpleDocTemplate(buffer)
    styles=getSampleStyleSheet()

    elements=[]
    elements.append(Paragraph("AI Resume Report",styles["Title"]))
    elements.append(Spacer(1,0.2*inch))
    elements.append(Paragraph(f"Role: {data['role']}",styles["Normal"]))
    elements.append(Paragraph(f"Score: {data['score']}%",styles["Normal"]))

    elements.append(Spacer(1,0.2*inch))
    elements.append(Paragraph("Missing Skills",styles["Heading2"]))

    table_data=[["Skills"]]+[[s] for s in data["missing"]]
    elements.append(Table(table_data))

    doc.build(elements)
    buffer.seek(0)

    return send_file(buffer,as_attachment=True,download_name="report.pdf")

# ---------------- TEXT EXTRACTION ----------------
def extract_text(filepath):
    text=""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            if page.extract_text():
                text+=page.extract_text()
    return text

if __name__=="__main__":
    app.run(debug=True)