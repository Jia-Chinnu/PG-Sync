from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector
from datetime import datetime

app = Flask(__name__)
app.secret_key = "pg_sync_secure"

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="pgsync_user",
        password="pgsync123",
        database="pg_sync",
        autocommit=True
    )


@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        role = request.form["role"].strip()

        db = get_db()
        cur = db.cursor(dictionary=True)


        cur.execute("SELECT id FROM users WHERE email=%s", (email,))
        if cur.fetchone():
            flash("Terminal Error: Account already exists for this email.", "error")
            return redirect(url_for("signup"))

        resident_db_id = None
        if role == "resident":
            cur.execute("""
                SELECT id FROM residents 
                WHERE email=%s AND user_id IS NULL 
                ORDER BY id DESC LIMIT 1
            """, (email,))
            resident_record = cur.fetchone()
            
            if not resident_record:
                flash("Sync Error: No pending profile found. Contact your PG owner.", "error")
                return redirect(url_for("signup"))
            
            resident_db_id = resident_record["id"]

        
        cur.execute("""
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """, (name, email, password, role))
        new_user_id = cur.lastrowid


        if role == "resident" and resident_db_id:
            cur.execute("""
                UPDATE residents 
                SET user_id=%s, verified=1 
                WHERE id=%s
            """, (new_user_id, resident_db_id))

        flash("Hub Account Created Successfully! Syncing Terminal...", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip()
        password = request.form["password"].strip()
        
        db = get_db()
        cur = db.cursor(dictionary=True)

    
        cur.execute("SELECT * FROM users WHERE email=%s AND password=%s", (email, password))
        user = cur.fetchone()

        if not user:
        
            flash("Administrator email or key not found.", "error")
            return redirect(url_for("login"))

        
        session.clear()
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        session["name"] = user["name"]
        session["email"] = user["email"]

        flash("Hub Sync Successful!", "success")

        
        if user["role"] == "owner":
            return redirect(url_for("owner_dashboard"))
        else:
            return redirect(url_for("resident_dashboard"))

    return render_template("login.html")

@app.route('/submit-complaint', methods=['POST'])
def submit_complaint():
    if session.get("role") != "resident":
        return redirect(url_for("login"))
        

    category = request.form.get('category')
    message = request.form.get('complaint_msg')
    
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    
    cur.execute("SELECT id FROM residents WHERE user_id = %s", (session["user_id"],))
    resident = cur.fetchone()

    if resident:
        
        cur.execute("""
            INSERT INTO complaints (resident_id, category, message, status) 
            VALUES (%s, %s, %s, 'pending')
        """, (resident['id'], category, message))
        db.commit() 
        flash("Complaint transmitted to owner.", "success")
    else:
        flash("Sync Error: Resident profile not found.", "error")
    
    return redirect(url_for('resident_dashboard'))

@app.route("/admin/reply-complaint/<int:complaint_id>", methods=["POST"])
def reply_complaint(complaint_id):
    if session.get("role") != "owner":
        return redirect(url_for("login"))
    
    reply_text = request.form.get("admin_reply")
    db = get_db()
    cur = db.cursor()
    
    
    cur.execute("""
        INSERT INTO complaint_messages (complaint_id, sender_role, message) 
        VALUES (%s, 'owner', %s)
    """, (complaint_id, reply_text))
    
    
    cur.execute("UPDATE complaints SET status='open' WHERE id=%s", (complaint_id,))
    
    flash("Reply sent. Conversation is now active.", "success")
    return redirect(url_for("owner_dashboard"))

@app.route("/resident/reply-complaint/<int:complaint_id>", methods=["POST"])
def resident_reply(complaint_id):
    if session.get("role") != "resident": return redirect(url_for("login"))
    
    msg = request.form.get("message")
    db = get_db(); cur = db.cursor()
    cur.execute("INSERT INTO complaint_messages (complaint_id, sender_role, message) VALUES (%s, 'resident', %s)", 
                (complaint_id, msg))
    flash("Message sent to owner.", "success")
    return redirect(url_for("resident_dashboard"))


@app.route("/resident/resolve-complaint/<int:complaint_id>", methods=["POST"])
def resolve_complaint(complaint_id):
    if session.get("role") != "resident": return redirect(url_for("login"))
    
    db = get_db(); cur = db.cursor()
    cur.execute("UPDATE complaints SET status='resolved' WHERE id=%s", (complaint_id,))
    flash("Glad you are satisfied! Ticket closed.", "success")
    return redirect(url_for("resident_dashboard"))



@app.route("/submit-late-reason/<int:pay_id>", methods=["POST"])
def submit_late_reason(pay_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))
    
    reason = request.form.get("reason_text")
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE payments SET reason=%s, status='overdue_rolling' WHERE id=%s", (f"LATE REASON: {reason}", pay_id))
    
    flash("Reason submitted. Balance will be reviewed for roll-over.", "warning")
    return redirect(url_for("resident_dashboard"))



@app.route("/owner-dashboard")
def owner_dashboard():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    owner_id = session["user_id"]
    db = get_db()
    cur = db.cursor(dictionary=True)

    
    cur.execute("SELECT * FROM properties WHERE owner_id = %s", (owner_id,))
    properties = cur.fetchall()
    
    prop_ids = [p['id'] for p in properties]
    
    if not prop_ids:
        return render_template("owner_dashboard.html", 
                               properties=[], payments=[], 
                               complaints=[], rooms=[], now=datetime.now())

    format_strings = ','.join(['%s'] * len(prop_ids))

    
    cur.execute(f"SELECT * FROM rooms WHERE property_id IN ({format_strings})", tuple(prop_ids))
    rooms = cur.fetchall()

    
    cur.execute(f"""
        SELECT p.id AS pay_id, u.name AS resident, r.resident_id, rm.room_no,
               b.title, b.month, p.amount, IFNULL(p.amount_paid,0) AS amount_paid, 
               p.status, r.property_id, p.created_at
        FROM payments p
        JOIN residents r ON p.resident_id=r.id
        JOIN users u ON r.user_id=u.id
        JOIN rooms rm ON r.room_id=rm.id
        JOIN bills b ON p.bill_id=b.id
        WHERE r.property_id IN ({format_strings})
        ORDER BY p.created_at DESC
    """, tuple(prop_ids))
    payments = cur.fetchall()

    for p in payments:
        p['due'] = float(p['amount']) - float(p['amount_paid'])

    
    cur.execute(f"""
        SELECT c.id, c.category, c.message, c.status, c.created_at,
               u.name as resident_name, rm.room_no 
        FROM complaints c
        JOIN residents r ON c.resident_id = r.id
        JOIN users u ON r.user_id = u.id
        JOIN rooms rm ON r.room_id = rm.id
        WHERE r.property_id IN ({format_strings}) AND c.status != 'resolved'
        ORDER BY c.created_at DESC
    """, tuple(prop_ids))
    complaints = cur.fetchall()

    
    
    for c in complaints:
        cur.execute("""
            SELECT sender_role, message, created_at 
            FROM complaint_messages 
            WHERE complaint_id = %s 
            ORDER BY created_at ASC
        """, (c['id'],))
        c['chat_history'] = cur.fetchall()

    
    for prop in properties:
        cur.execute("""
            SELECT SUM(p.amount) as total, SUM(p.amount_paid) as paid 
            FROM payments p 
            JOIN residents r ON p.resident_id = r.id 
            WHERE r.property_id = %s
        """, (prop['id'],))
        stats = cur.fetchone()
        
        total = float(stats['total'] or 0)
        paid = float(stats['paid'] or 0)
        
        if total > 0:
            prop['profit_percent'] = round((paid / total) * 100, 1)
            prop['loss_percent'] = round(100 - prop['profit_percent'], 1)
        else:
            prop['profit_percent'] = 0
            prop['loss_percent'] = 100

    return render_template("owner_dashboard.html", 
                           properties=properties, rooms=rooms, 
                           payments=payments, complaints=complaints,
                           now=datetime.now())

@app.route("/add-resident", methods=["POST"])
def add_resident():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    
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

@app.route("/add-bills", methods=["POST"])
def add_bills():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    bill_names = request.form.getlist('bill_names[]')
    bill_amounts = request.form.getlist('bill_amounts[]')
    room_id = request.form.get("room_id")

    if not bill_names or not bill_amounts or not room_id:
        flash("HUB ERROR: Missing billing parameters.", "error")
        return redirect(url_for("owner_dashboard"))

    try:
        total_bill_value = sum(float(amt) for amt in bill_amounts if amt)
        combined_title = ", ".join(bill_names)
        current_month = datetime.now().strftime("%B %Y")

        cur.execute("SELECT id, property_id FROM residents WHERE room_id = %s", (room_id,))
        residents = cur.fetchall()

        if not residents:
            flash("HUB ERROR: No residents found in this room.", "error")
            return redirect(url_for("owner_dashboard"))

        cur.execute("""
            INSERT INTO bills (title, amount, month, property_id) 
            VALUES (%s, %s, %s, %s)
        """, (combined_title, total_bill_value, current_month, residents[0]['property_id']))
        bill_id = cur.lastrowid

        split_per_person = total_bill_value / len(residents)

        for res in residents:
            cur.execute("""
                INSERT INTO payments (resident_id, bill_id, amount, status, created_at) 
                VALUES (%s, %s, %s, 'pending', NOW())
            """, (res['id'], bill_id, split_per_person))

        flash(f"SYNC AUTHORIZED: ₹{total_bill_value} split successfully.", "success")
    except Exception as e:
        flash(f"HUB DATABASE ERROR: {str(e)}", "error")

    return redirect(url_for("owner_dashboard"))
@app.route("/add-room", methods=["POST"])
def add_room():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    try:
        cur.execute("""
            INSERT INTO rooms (room_no, capacity, property_id)
            VALUES (%s, %s, %s)
        """, (request.form["room_no"],
              request.form["capacity"],
              request.form["property_id"]))
        flash("Room initialized in your Asset Hub.", "success")
    except Exception as e:
        flash(f"Sync Error: {str(e)}", "error")
        
    return redirect(url_for("owner_dashboard"))

@app.route("/settle-split/<int:split_id>")
def settle_split(split_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    cur.execute("SELECT id FROM private_settlements WHERE split_id=%s AND resident_name=%s", 
               (split_id, session['name']))
    if cur.fetchone():
        flash("You have already synced this payment.", "warning")
        return redirect(url_for("resident_dashboard"))

    
    cur.execute("""
        INSERT INTO private_settlements (split_id, resident_name, status)
        VALUES (%s, %s, 'paid')
    """, (split_id, session['name']))

    flash("Sync Successful! Your payment is now visible to the initiator.", "success")
    return redirect(url_for("resident_dashboard"))


@app.route("/verify-transaction/<int:id_type>/<int:sync_id>", methods=["POST"])
def verify_transaction(id_type, sync_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)
    utr_id = request.form.get("utr_id")

    if not utr_id or len(utr_id) < 10:
        flash("Invalid Transaction ID. Please enter the 12-digit UTR.", "error")
        return redirect(url_for("resident_dashboard"))

    
    if id_type == 1:
        cur.execute("UPDATE payments SET status='paid', amount_paid=amount, reason=%s WHERE id=%s", (f"UTR: {utr_id}", sync_id))
    else:
        cur.execute("INSERT INTO private_settlements (split_id, resident_name, status) VALUES (%s, %s, %s)", 
                   (sync_id, session['name'], f"UTR: {utr_id}"))

    flash(f"Sync Verified! Transaction {utr_id} recorded.", "success")
    return redirect(url_for("resident_dashboard"))

@app.route("/resident-dashboard", methods=["GET", "POST"])
def resident_dashboard():
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    
    cur.execute("""
        SELECT r.id, r.resident_id, r.room_id, rm.room_no, u.name 
        FROM residents r 
        JOIN rooms rm ON r.room_id = rm.id 
        JOIN users u ON r.user_id = u.id
        WHERE r.user_id = %s
    """, (session["user_id"],))
    resident = cur.fetchone()


    cur.execute("""
        SELECT u.name FROM residents r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.room_id = %s
    """, (resident['room_id'],))
    room_roster = [row['name'] for row in cur.fetchall()]

    
    cur.execute("""
        SELECT id, category, message, status, created_at 
        FROM complaints 
        WHERE resident_id = %s 
        ORDER BY created_at DESC
    """, (resident['id'],))
    my_complaints = cur.fetchall()

    for c in my_complaints:
        
        cur.execute("""
            SELECT sender_role, message, created_at 
            FROM complaint_messages 
            WHERE complaint_id = %s 
            ORDER BY created_at ASC
        """, (c['id'],))
        c['chat_history'] = cur.fetchall()

    
    cur.execute("SELECT id, resident_name, title, amount_per_person, created_at FROM private_splits WHERE room_id = %s ORDER BY created_at DESC", (resident['room_id'],))
    splits = cur.fetchall()
    
    for s in splits:
        cur.execute("SELECT resident_name FROM private_settlements WHERE split_id = %s", (s['id'],))
        paid_list = [row['resident_name'] for row in cur.fetchall()]
        
        s['full_ledger'] = []
        for member in room_roster:
            is_paid = (member == s['resident_name']) or (member in paid_list)
            s['full_ledger'].append({
                'name': member,
                'is_paid': is_paid,
                'is_initiator': (member == s['resident_name'])
            })
        s['user_has_paid'] = session['name'] in paid_list or session['name'] == s['resident_name']

    
    cur.execute("SELECT COUNT(*) as count FROM residents WHERE room_id = %s", (resident['room_id'],))
    resident_count = cur.fetchone()['count']
    
    cur.execute("""
        SELECT p.id AS pay_id, p.amount, p.amount_paid, p.status, p.created_at, b.title, b.month 
        FROM payments p 
        JOIN bills b ON p.bill_id = b.id 
        WHERE p.resident_id = %s 
        ORDER BY p.created_at DESC
    """, (resident["id"],))
    payments = cur.fetchall()

    return render_template("resident.html", 
                           resident=resident, 
                           payments=payments, 
                           resident_count=resident_count, 
                           private_splits=splits,
                           my_complaints=my_complaints)

@app.route("/broadcast-private-split", methods=["POST"])
def broadcast_private_split():
    
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

   
    cur.execute("SELECT room_id FROM residents WHERE user_id = %s", (session["user_id"],))
    resident = cur.fetchone()

    
    target_upi = "jiachinnu999@oksbi" 

    
    title = request.form.get("title", "").strip()
    amount = request.form.get("amount", "")

    
    if not title or not amount:
        flash("Sync Hub Error: Missing description or amount.", "error")
        return redirect(url_for("resident_dashboard"))

    try:
        
        cur.execute("""
            INSERT INTO private_splits 
            (room_id, resident_name, upi_target, title, amount_per_person, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (
            resident['room_id'], 
            session.get('name', 'Resident'), 
            target_upi, 
            title, 
            amount
        ))
        
        flash(f"Success: '{title}' split has been broadcasted to your roommates.", "success")
        
    except Exception as e:
        
        flash(f"Terminal Error: {str(e)}", "error")

    return redirect(url_for("resident_dashboard"))


@app.route("/pay-bill/<int:pay_id>")
def pay_bill(pay_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    
    
    cur.execute("UPDATE payments SET status='paid', amount_paid=amount WHERE id=%s", (pay_id,))
    
    flash("Terminal Sync Successful: Receipt generated for Owner.", "success")
    return redirect(url_for("resident_dashboard"))
@app.route("/pay-roommate-split/<int:split_id>")
def pay_roommate_split(split_id):
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    
    cur.execute("SELECT id FROM residents WHERE user_id = %s", (session["user_id"],))
    payer = cur.fetchone()

    
    cur.execute("""
        INSERT INTO private_settlements (split_id, resident_id, status)
        VALUES (%s, %s, 'paid')
    """, (split_id, payer['id']))

    flash("Sync Successful! Your payment has been recorded in the Room Hub.", "success")
    return redirect(url_for("resident_dashboard"))
@app.route("/add-property", methods=["POST"])
def add_property():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    name = request.form["property_name"]
    address = request.form["address"]
    phone = request.form["phone"]
    owner_id = session["user_id"] 

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO properties (name, address, phone, owner_id) 
        VALUES (%s, %s, %s, %s)
    """, (name, address, phone, owner_id))
    
    flash(f"Asset {name} deployed to your terminal.", "success")
    return redirect(url_for("owner_dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect("/")


if __name__ == "__main__":
    app.run(debug=True)
