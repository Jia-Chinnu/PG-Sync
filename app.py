from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "pg_sync_secure"

# ---------------- DATABASE ----------------
def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="pgsync_user",
        password="pgsync123",
        database="pg_sync",
        autocommit=True
    )

# ---------------- LANDING ----------------
@app.route("/")
def landing():
    return render_template("landing.html")

# ---------------- SIGNUP ----------------
from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector

@app.route("/signup", methods=["GET", "POST"])
def signup():
    db = get_db()
    cur = db.cursor(dictionary=True)

    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        role = request.form["role"].strip()

        # Prevent duplicate email in users table
        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Email already registered", "error")
            return redirect(url_for("signup"))

        # Insert new user
        cur.execute("""
            INSERT INTO users (name,email,password,role)
            VALUES (%s,%s,%s,%s)
        """, (name, email, password, role))
        user_id = cur.lastrowid

        # Auto-link resident if role is resident
        if role == "resident":
            # First try linking by resident_id if provided
            resident_uid = request.form.get("resident_id", "").strip()
            resident = None

            if resident_uid:
                cur.execute("""
                    SELECT id FROM residents
                    WHERE resident_id=%s AND user_id IS NULL
                """, (resident_uid,))
                resident = cur.fetchone()

            # Fallback: link by email if resident_id not provided or not found
            if not resident:
                cur.execute("""
                    SELECT id FROM residents
                    WHERE email=%s AND user_id IS NULL
                """, (email,))
                resident = cur.fetchone()

            if not resident:
                flash("Resident profile not created by owner or already linked", "error")
                return redirect(url_for("signup"))

            # Link user to resident
            cur.execute("""
                UPDATE residents
                SET user_id=%s, verified=1
                WHERE id=%s
            """, (user_id, resident["id"]))

        flash("Signup successful! Please login.", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        db = get_db()
        cur = db.cursor(dictionary=True)

        cur.execute("""
            SELECT * FROM users
            WHERE email=%s AND password=%s
        """, (request.form["email"],request.form["password"]))
        user = cur.fetchone()

        if not user:
            flash("Invalid email or password", "error")
            return redirect(url_for("login"))

        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]
        session["email"] = user["email"]

        flash("Login successful!", "success")

        return redirect(
            url_for("owner_dashboard") if user["role"]=="owner"
            else url_for("resident_dashboard")
        )

    return render_template("login.html")

# ---------------- OWNER DASHBOARD ----------------
@app.route("/owner-dashboard")
def owner_dashboard():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT p.id AS pay_id,
               u.name AS resident,
               r.resident_id,
               rm.room_no,
               b.title,
               b.month,
               p.amount,
               IFNULL(p.amount_paid,0) AS amount_paid,
               p.status
        FROM payments p
        JOIN residents r ON p.resident_id=r.id
        JOIN users u ON r.user_id=u.id
        JOIN rooms rm ON r.room_id=rm.id
        JOIN bills b ON p.bill_id=b.id
        ORDER BY b.month DESC
    """)
    payments = cur.fetchall()

    for p in payments:
        p["due"] = p["amount"] - p["amount_paid"]

    cur.execute("SELECT * FROM properties")
    properties = cur.fetchall()

    cur.execute("SELECT * FROM rooms")
    rooms = cur.fetchall()

    return render_template(
        "owner_dashboard.html",
        payments=payments,
        properties=properties,
        rooms=rooms
    )

# ---------------- ADD PROPERTY ----------------
@app.route("/add-property", methods=["POST"])
def add_property():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute(
        "INSERT INTO properties (name,address,phone) VALUES (%s,%s,%s)",
        (
            request.form["property_name"],
            request.form.get("address",""),
            request.form.get("phone","")   # <-- include phone
        )
    )
    flash("Property added successfully!", "success")
    return redirect(url_for("owner_dashboard"))


# ---------------- ADD ROOM ----------------
@app.route("/add-room", methods=["POST"])
def add_room():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO rooms (room_no,capacity,property_id)
        VALUES (%s,%s,%s)
    """,(request.form["room_no"],
         request.form["capacity"],
         request.form["property_id"]))
    flash("Room added successfully", "success")
    return redirect(url_for("owner_dashboard"))

# ---------------- ADD RESIDENT ----------------
@app.route("/add-resident", methods=["POST"])
def add_resident():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    # AUTO GENERATE resident_id
    cur.execute("""
        SELECT MAX(CAST(SUBSTRING(resident_id,4) AS UNSIGNED)) AS last
        FROM residents
    """)
    last = cur.fetchone()["last"] or 0
    resident_id = f"RES{last+1:03d}"

    cur.execute("""
        INSERT INTO residents (resident_id,email,property_id,room_id)
        VALUES (%s,%s,%s,%s)
    """,(resident_id,
         request.form["email"],
         request.form["property_id"],
         request.form["room_id"]))

    flash(f"Resident added successfully. Resident ID: {resident_id}", "success")
    return redirect(url_for("owner_dashboard"))

# ---------------- RESIDENT DASHBOARD ----------------
@app.route("/resident-dashboard", methods=["GET","POST"])
def resident_dashboard():
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("""
        SELECT r.id,r.resident_id,rm.room_no,p.name AS property
        FROM residents r
        JOIN rooms rm ON r.room_id=rm.id
        JOIN properties p ON r.property_id=p.id
        WHERE r.user_id=%s
    """,(session["user_id"],))
    resident = cur.fetchone()

    if not resident:
        return "Resident profile not setup. Contact owner."

    cur.execute("""
        SELECT p.id AS pay_id,p.amount,p.amount_paid,p.status,p.reason,
               b.title,b.month
        FROM payments p
        JOIN bills b ON p.bill_id=b.id
        WHERE p.resident_id=%s
        ORDER BY b.month DESC
    """,(resident["id"],))
    payments = cur.fetchall()

    if request.method == "POST":
        if "complaint" in request.form:
            cur.execute("""
                INSERT INTO complaints (resident_id,complaint,created_at)
                VALUES (%s,%s,NOW())
            """,(resident["id"],request.form["complaint"]))
            flash("Complaint submitted successfully", "success")

        if "reason" in request.form:
            cur.execute("""
                UPDATE payments SET reason=%s WHERE id=%s
            """,(request.form["reason"],request.form["payment_id"]))
            flash("Reason updated", "success")

        return redirect(url_for("resident_dashboard"))

    return render_template("resident.html", resident=resident, payments=payments)

# ---------------- PAY BILL ----------------
@app.route("/pay-bill/<int:pay_id>")
def pay_bill(pay_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        UPDATE payments
        SET status='paid',amount_paid=amount
        WHERE id=%s
    """,(pay_id,))
    flash("Payment marked as paid", "success")
    return redirect(url_for("resident_dashboard"))

# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect("/")

# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
