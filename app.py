from flask import Flask, render_template, request, redirect, session, url_for, flash
from flask_mail import Mail, Message
from flask_apscheduler import APScheduler
import mysql.connector
from datetime import datetime, timedelta
import socket
import os
import pytesseract
from PIL import Image
import re
import cv2
import numpy as np
from sklearn.linear_model import LinearRegression

app = Flask(__name__)
app.secret_key = "pg_sync_secure"

# --- 1. DYNAMIC IP DETECTION ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

LOCAL_IP = get_local_ip()

# --- 2. CONFIGURATIONS ---
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'bills')
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'jiachinnu999@gmail.com' 
app.config['MAIL_PASSWORD'] = 'qcsavkleuqibbxjw' 
app.config['MAIL_DEFAULT_SENDER'] = ('PG Sync Pro Billing', 'jiachinnu999@gmail.com')

mail = Mail(app)

# --- 3. SCHEDULER SETUP ---
app.config['SCHEDULER_API_ENABLED'] = True
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

# Database Connection
# Database Connection
# Database Connection
def get_db():
    return mysql.connector.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        autocommit=True
    )
# --- 4. CORE NOTIFICATION ENGINE ---
def send_detailed_billing_emails():
    """Loops through residents and sends full invoice breakdown"""
    with app.app_context():
        db = get_db()
        cur = db.cursor(dictionary=True)
        month_label = datetime.now().strftime("%B %Y")
        
        cur.execute("""
            SELECT u.name, r.email, p.amount, p.current_amount, p.arrear_amount, p.fine_amount, b.title 
            FROM residents r
            JOIN users u ON r.user_id = u.id
            JOIN payments p ON r.id = p.resident_id
            JOIN bills b ON p.bill_id = b.id
            WHERE p.status = 'pending' AND b.month = %s
        """, (month_label,))
        
        records = cur.fetchall()
        if not records:
            print(f"Sync: No pending bills found for {month_label}.")
            return

        for res in records:
            if not res['email']: continue
            msg = Message(subject=f"Monthly Rent Statement - {month_label}",
                          recipients=[res['email']])

            msg.html = f"""
            <div style="font-family: 'Segoe UI', Arial, sans-serif; max-width: 600px; border: 1px solid #ddd; padding: 30px; border-radius: 12px; background-color: #ffffff;">
                <h2 style="color: #008730; border-bottom: 2px solid #008730; padding-bottom: 10px; margin-top: 0;">PG SYNC PRO INVOICE</h2>
                <p>Hello <b>{res['name']}</b>,</p>
                <p>Your billing breakdown for <b>{month_label}</b> is as follows:</p>
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #f8f9fa;">
                        <th style="padding: 12px; border: 1px solid #ddd; text-align: left;">Item</th>
                        <th style="padding: 12px; border: 1px solid #ddd; text-align: right;">Amount (₹)</th>
                    </tr>
                    <tr><td style="padding: 12px; border: 1px solid #ddd;">Current {res['title']}</td><td style="padding: 12px; border: 1px solid #ddd; text-align: right;">{float(res['current_amount']):.2f}</td></tr>
                    <tr><td style="padding: 12px; border: 1px solid #ddd;">Previous Dues (Arrears)</td><td style="padding: 12px; border: 1px solid #ddd; text-align: right;">{float(res['arrear_amount']):.2f}</td></tr>
                    <tr><td style="padding: 12px; border: 1px solid #ddd;">Late Penalties</td><td style="padding: 12px; border: 1px solid #ddd; text-align: right;">{float(res['fine_amount']):.2f}</td></tr>
                    <tr style="font-weight: bold; background-color: #e6f4ea; font-size: 1.1em;">
                        <td style="padding: 12px; border: 1px solid #ddd;">TOTAL PAYABLE</td>
                        <td style="padding: 12px; border: 1px solid #ddd; text-align: right; color: #008730;">₹{float(res['amount']):.2f}</td>
                    </tr>
                </table>
                <div style="background-color: #fff5f5; border-left: 5px solid #ff4757; padding: 15px; margin: 20px 0; border-radius: 4px;">
                    <b style="color: #ff4757;">⚠️ LATE FEE NOTICE:</b><br>
                    Payments must be synced before the 10th of this month to avoid a <b>₹100 fine</b>.
                </div>
                <p style="text-align: center; margin-top: 25px;">
                    <a href="http://{LOCAL_IP}:5000/login" style="background-color: #008730; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">ACCESS RESIDENT DASHBOARD</a>
                </p>
            </div>
            """
            try:
                mail.send(msg)
                print(f"Sync: Email dispatched to {res['email']}")
            except Exception as e:
                print(f"Error: Could not send to {res['email']}: {e}")



@app.route("/test-billing-email")
def test_billing_email():
    """Route to manually trigger emails for the teacher demo"""
    try:
        send_detailed_billing_emails()
        return "<h1>Success!</h1><p>Check your console and inbox.</p>"
    except Exception as e:
        return f"<h1>Failed</h1><p>Error: {str(e)}</p>"

# --- 6. AUTOMATED TASK (1st of every month) ---
@scheduler.task('cron', id='billing_cycle', day='1', hour='10', minute='0')
def scheduled_notif():
    print("Executing automatic monthly billing reminders...")
    send_detailed_billing_emails()

# --- 7. RUNNER (Must be at the absolute bottom) ---

# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


# -------------------------------
# AUTO CROP TEXT REGIONS
# -------------------------------
def crop_text_regions(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return image_path

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detect edges
    edges = cv2.Canny(gray, 50, 150)

    # Dilate to merge text areas
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    dilated = cv2.dilate(edges, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    h, w = gray.shape
    candidates = []

    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)

        # Filter: wide boxes likely contain totals
        if cw > w * 0.3 and ch > h * 0.03:
            candidates.append((x, y, cw, ch))

    if not candidates:
        return image_path

    # Sort bottom-most region (totals usually at bottom)
    candidates = sorted(candidates, key=lambda b: b[1], reverse=True)

    x, y, cw, ch = candidates[0]

    cropped = img[y:y+ch, x:x+cw]

    crop_path = image_path.replace(".png", "_crop.png")
    cv2.imwrite(crop_path, cropped)

    return crop_path


# -------------------------------
# PREPROCESS
# -------------------------------
def preprocess(img):
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=20)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)

    _, thresh = cv2.threshold(blur, 150, 255, cv2.THRESH_BINARY)

    return thresh


# -------------------------------
# OCR ENGINE
# -------------------------------
def extract_amount(text):
    text = text.replace(",", "")
    lines = text.split("\n")

    # PRIORITY SEARCH
    for line in lines:
        if any(k in line for k in ["TOTAL", "PAYABLE", "AMOUNT", "RS"]):
            nums = re.findall(r'\d{2,6}(?:\.\d{1,2})?', line)
            if nums:
                val = float(nums[-1])
                if 50 < val < 50000:
                    return val

    # FALLBACK
    nums = re.findall(r'\d{2,6}(?:\.\d{1,2})?', text)
    values = [float(n) for n in nums if 50 < float(n) < 50000]

    return max(values) if values else 0.0


# -------------------------------
# MAIN SCAN FUNCTION
# -------------------------------
def perform_live_scan(image_path, bill_type=None):
    try:
        # STEP 1: Crop likely total region
        cropped_path = crop_text_regions(image_path)

        img = cv2.imread(cropped_path)
        if img is None:
            return {"verified": False, "amount": 0.0}

        # STEP 2: preprocess
        processed = preprocess(img)

        cv2.imwrite("debug_processed.png", processed)

        # STEP 3: OCR
        text = pytesseract.image_to_string(
            processed,
            config='--oem 3 --psm 11'
        ).upper()

        print("\n==== OCR TEXT ====\n", text, "\n==================\n")

        amount = extract_amount(text)

        if amount > 0:
            return {"verified": True, "amount": amount}

        return {"verified": False, "amount": 0.0}

    except Exception as e:
        print("OCR ERROR:", e)
        return {"verified": False, "amount": 0.0}


# -------------------------------
@app.route("/upload-utility-bill", methods=["POST"])
def upload_utility_bill():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    # 1. Get Form Data
    file = request.files.get("bill_doc")
    bill_type = request.form.get("bill_type", "").strip()
    month_year = datetime.now().strftime("%B %Y")
    
    # 2. MANDATORY DEFAULTS
    defaults = {
        "KSEB Electricity": 2249.0,
        "KWA Water": 1510.0,
        "Asianet WiFi": 5000.0
    }

    if not file:
        flash("No file uploaded", "error")
        return redirect(url_for("owner_dashboard"))

    # 3. SAVE THE FILE
    filename = f"scan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # 4. OCR / DEFAULT CALCULATION
    try:
        result = perform_live_scan(filepath, bill_type)
        total = result["amount"] if result["amount"] > 0 else defaults.get(bill_type, 0.0)
    except:
        total = defaults.get(bill_type, 0.0)

    db = get_db()
    cur = db.cursor(dictionary=True)

    # 5. FETCH ALL REGISTERED RESIDENTS
    cur.execute("""
        SELECT r.id, r.property_id 
        FROM residents r
        JOIN properties p ON r.property_id = p.id
        WHERE p.owner_id = %s AND r.user_id IS NOT NULL
    """, (session["user_id"],))
    residents = cur.fetchall()

    if not residents:
        flash("Error: No residents found to split with.", "error")
        return redirect(url_for("owner_dashboard"))

    # 6. CALCULATE THE SPLIT
    count = len(residents)
    per_head = round(total / count, 2)
    prop_id = residents[0]["property_id"]

    try:
        # 7. INSERT MASTER BILL
        cur.execute("""
            INSERT INTO bills (title, amount, month, property_id, bill_image)
            VALUES (%s, %s, %s, %s, %s)
        """, (f"{bill_type} Bill", total, month_year, prop_id, filename))
        bill_id = cur.lastrowid

        # 8. INSERT PAYMENTS (ONE FOR EACH RESIDENT)
        for r in residents:
            # We pass per_head to both 'amount' and 'current_amount'
            # This ensures the dashboard breakdown label is NOT ₹0.00
            cur.execute("""
                INSERT INTO payments 
                (resident_id, bill_id, amount, current_amount, arrear_amount, fine_amount, amount_paid, status, month_year)
                VALUES (%s, %s, %s, %s, 0.0, 0.0, 0.0, 'pending', %s)
            """, (r["id"], bill_id, per_head, per_head, month_year))

        db.commit()
        flash(f"Split Executed: ₹{total} shared among {count} residents.", "success")

    except Exception as e:
        db.rollback()
        flash(f"Sync Error: {str(e)}", "error")

    return redirect(url_for("owner_dashboard"))


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

@app.route("/")
def landing():
    return render_template("landing.html")
 # Redirect to your landing page
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

@app.route("/owner/apply-fine/<int:pay_id>")
def apply_fine(pay_id):
    if session.get("role") != "owner": 
        return redirect(url_for("login"))
    
    db = get_db()
    cur = db.cursor(dictionary=True)
    
    # Check current fine status
    cur.execute("SELECT fine_amount, status FROM payments WHERE id = %s", (pay_id,))
    payment = cur.fetchone()
    
    if not payment:
        flash("Record not found.", "error")
        return redirect(url_for("owner_dashboard"))

    # Logic: Add 100 to whatever fine already exists
    new_fine = float(payment['fine_amount']) + 100.00
    
    cur.execute("""
        UPDATE payments 
        SET fine_amount = %s, status = 'late_approved' 
        WHERE id = %s
    """, (new_fine, pay_id))
    
    db.commit()
    flash(f"Success: Fine of +100 applied. Total fine: {new_fine}", "success")
    return redirect(url_for("owner_dashboard"))
@app.route("/owner/roll-over/<int:pay_id>")
def roll_over(pay_id):
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    # 1️⃣ Get unpaid old bill
    cur.execute("SELECT * FROM payments WHERE id=%s", (pay_id,))
    old = cur.fetchone()

    if not old:
        return redirect(url_for("dashboard"))

    arrear_amount = old["amount"]
    fine_amount = 100

    from datetime import datetime

    current_month = datetime.strptime(old["month"], "%B %Y")

    # 2️⃣ Calculate next month dynamically
    if current_month.month == 12:
        next_month = datetime(current_month.year + 1, 1, 1)
    else:
        next_month = datetime(current_month.year, current_month.month + 1, 1)

    next_month_str = next_month.strftime("%B %Y")

    # 3️⃣ Find next month bill with SAME title keyword
    cur.execute("""
        SELECT * FROM payments
        WHERE resident=%s 
        AND month=%s 
        AND title LIKE %s
        AND status='pending'
    """, (old["resident"], next_month_str, f"%{old['title'].split()[0]}%"))

    next_bill = cur.fetchone()

    if not next_bill:
        return redirect(url_for("dashboard"))

    current_month_amount = next_bill["amount"]

    # 4️⃣ Calculate total
    total_amount = arrear_amount + current_month_amount + fine_amount

    # 5️⃣ Create breakdown
    new_title = f"""Arrear from {old['month']} ₹{arrear_amount:.2f}
+ {next_month_str} Bill ₹{current_month_amount:.2f}
+ Fine ₹{fine_amount:.2f}
= ₹{total_amount:.2f}"""

    # 6️⃣ Update next month bill
    cur.execute("""
        UPDATE payments
        SET amount=%s, title=%s
        WHERE id=%s
    """, (total_amount, new_title, next_bill["id"]))

    # 7️⃣ Mark old bill as rolled
    cur.execute("UPDATE payments SET status='rolled_over' WHERE id=%s", (pay_id,))

    db.commit()
    return redirect(url_for("dashboard"))
@app.route("/owner-dashboard")
def owner_dashboard():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    # --- 1. TIMELINE & POLICY CHECKS ---
    today_day = datetime.now().day
    show_billing_alert = (today_day == 2)
    is_late_phase = (today_day >= 31) 

    owner_id = session["user_id"]
    db = get_db()
    # Ensure dictionary=True is used to prevent 'string to float' errors with column names
    cur = db.cursor(dictionary=True, buffered=True)

    # --- 2. BILLING CYCLE CHECK ---
    current_month_label = datetime.now().strftime("%B %Y")
    cur.execute("SELECT id FROM bills WHERE month = %s LIMIT 1", (current_month_label,))
    billed_this_month = cur.fetchone() is not None

    # --- 3. FETCH PROPERTIES ---
    cur.execute("SELECT * FROM properties WHERE owner_id = %s", (owner_id,))
    properties = cur.fetchall()
    
    predicted_total = 0.0
    if properties:
        try:
            predicted_total = ai_predict_bill(properties[0]['id']) 
        except:
            predicted_total = 2800.0

    # --- 4. HIERARCHY, ANALYTICS & RESIDENT SYNC ---
    for prop in properties:
        cur.execute("""
            SELECT r.*, 
            (SELECT COUNT(*) FROM residents WHERE room_id = r.id AND user_id IS NOT NULL) as real_resident_count 
            FROM rooms r WHERE r.property_id = %s
        """, (prop['id'],))
        prop_rooms = cur.fetchall()
        
        for room in prop_rooms:
            cur.execute("""
                SELECT 
                    p.id, r.resident_id, u.name AS resident, b.title, b.month, b.bill_image,
                    p.amount, p.amount_paid, p.status, p.created_at, 
                    p.fine_amount, p.current_amount, p.arrear_amount,
                    r.rollovers_used
                FROM payments p
                JOIN residents r ON p.resident_id = r.id
                JOIN users u ON r.user_id = u.id
                JOIN bills b ON p.bill_id = b.id
                WHERE r.room_id = %s
                ORDER BY p.created_at DESC
            """, (room['id'],))

            # Fetch the results - since cursor is dictionary=True, this returns a list of dicts
            payments_list = cur.fetchall()
            
            for pay in payments_list:
                # Use .get() or direct access with float conversion to handle potential None values
                # This ensures we are converting the DATA (e.g., 8000.0) and not the KEY ("amount")
                amt = float(pay.get('amount') or 0)
                paid = float(pay.get('amount_paid') or 0)
                fine = float(pay.get('fine_amount') or 0)
                
                base_due = amt - paid
                pay['due'] = base_due + fine
            
            room['payments'] = payments_list
        
        prop['rooms_data'] = prop_rooms

        # Portfolio Health
        cur.execute("""
            SELECT SUM(p.amount + IFNULL(p.fine_amount, 0)) as total, SUM(p.amount_paid) as paid 
            FROM payments p 
            JOIN residents r ON p.resident_id = r.id 
            WHERE r.property_id = %s
        """, (prop['id'],))
        stats = cur.fetchone()
        
        t = float(stats['total'] or 0.1)
        p_amt = float(stats['paid'] or 0)
        prop['profit_percent'] = round((p_amt / t * 100), 1)
        prop['loss_percent'] = 100 - prop['profit_percent']

    # --- 5. COMPLIANCE LIST ---
    cur.execute("""
        SELECT r.id as resident_id, u.name, r.rollovers_used, rm.room_no, p.name as property_name
        FROM residents r
        JOIN users u ON r.user_id = u.id
        JOIN rooms rm ON r.room_id = rm.id
        JOIN properties p ON rm.property_id = p.id
        WHERE p.owner_id = %s
        ORDER BY r.rollovers_used DESC
    """, (owner_id,))
    compliance_list = cur.fetchall()

    # --- 6. DROPDOWN & COMPLAINTS ---
    cur.execute("""
        SELECT r.id, r.room_no, r.property_id, p.name as prop_name 
        FROM rooms r 
        JOIN properties p ON r.property_id = p.id 
        WHERE p.owner_id = %s
    """, (owner_id,))
    all_rooms = cur.fetchall()

    cur.execute("""
        SELECT c.*, COALESCE(u.name, r.email) as resident_name, rm.room_no, pr.name as property_name 
        FROM complaints c
        JOIN residents r ON c.resident_id = r.id 
        LEFT JOIN users u ON r.user_id = u.id
        JOIN rooms rm ON r.room_id = rm.id 
        JOIN properties pr ON rm.property_id = pr.id
        WHERE pr.owner_id = %s
        ORDER BY c.created_at DESC
    """, (owner_id,))
    complaints = cur.fetchall()

    return render_template("owner_dashboard.html", 
                           properties=properties, 
                           rooms=all_rooms, 
                           complaints=complaints,
                           compliance_list=compliance_list,
                           predicted_total=predicted_total, 
                           billed_this_month=billed_this_month,
                           show_billing_alert=show_billing_alert,
                           is_late_phase=is_late_phase)
def ai_predict_bill(property_id):
    """
    Predicts the next bill amount based on history.
    Kept to prevent NameError in the dashboard sidebar.
    """
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT amount FROM bills WHERE property_id = %s ORDER BY id DESC LIMIT 6", (property_id,))
    history = cur.fetchall()
    
    if len(history) < 2:
        return 2800.0  # Default demo value
    
    y = np.array([float(h['amount']) for h in history]).reshape(-1, 1)
    x = np.array(range(len(history))).reshape(-1, 1)
    model = LinearRegression().fit(x, y)
    prediction = model.predict(np.array([[len(history)]]))
    return float(prediction[0][0])
@app.route("/add-bills", methods=["POST"])
def add_bills():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    bill_names = request.form.getlist('bill_names[]')
    bill_amounts = request.form.getlist('bill_amounts[]')
    room_id = request.form.get("room_id")

    try:
        custom_title = bill_names[0].strip() if bill_names[0] else "Monthly Rent"
        base_total = sum(float(amt) for amt in bill_amounts if amt)
        current_month = datetime.now().strftime("%B %Y")

        cur.execute("SELECT id, property_id FROM residents WHERE room_id = %s", (room_id,))
        residents = cur.fetchall()

        if not residents:
            flash("Error: No residents found in this room.", "error")
            return redirect(url_for("owner_dashboard"))

        # Insert Master Bill
        cur.execute("INSERT INTO bills (title, amount, month, property_id) VALUES (%s, %s, %s, %s)",
                   (custom_title, base_total, current_month, residents[0]['property_id']))
        bill_id = cur.lastrowid
        
        # This is the 'Current' split for this month
        split_per_person = base_total / len(residents)

        for res in residents:
            arrear_val = 0.0
            fine_val = 0.0
            
            # Find previous pending bills with the SAME title to roll over debt
            cur.execute("""
                SELECT p.id, p.amount FROM payments p
                JOIN bills b ON p.bill_id = b.id
                WHERE p.resident_id = %s AND p.status = 'pending' AND b.title = %s
                ORDER BY p.id DESC LIMIT 1
            """, (res['id'], custom_title))
            previous = cur.fetchone()

            if previous:
                arrear_val = float(previous['amount'])
                fine_val = 100.0  
                cur.execute("UPDATE payments SET status = 'rolled_over' WHERE id = %s", (previous['id'],))

            total_payable = split_per_person + arrear_val + fine_val

            # ADDED: current_amount column to store the split_per_person
            cur.execute("""
                INSERT INTO payments (resident_id, bill_id, amount, current_amount, arrear_amount, fine_amount, status, month_year, created_at) 
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s, NOW())
            """, (res['id'], bill_id, total_payable, split_per_person, arrear_val, fine_val, current_month))

        db.commit()
        flash(f"SYNC: {custom_title} distributed. Breakdown populated.", "success")
        
    except Exception as e:
        db.rollback()
        flash(f"DATABASE ERROR: {str(e)}", "error")

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
    utr_id = request.form.get("utr_id").strip()

    # METHOD A: Strict 12-digit numeric validation
    if not utr_id.isdigit() or len(utr_id) != 12:
        flash("Google Pay Sync Error: UTR must be exactly 12 digits.", "error")
        return redirect(url_for("resident_dashboard"))

    # Update payment status
    if id_type == 1:
        cur.execute("UPDATE payments SET status='paid', amount_paid=amount, reason=%s WHERE id=%s", 
                   (f"UTR: {utr_id}", sync_id))
    else:
        cur.execute("INSERT INTO private_settlements (split_id, resident_name, status) VALUES (%s, %s, %s)", 
                   (sync_id, session['name'], f"UTR: {utr_id}"))

    db.commit()
    
    # Redirect to the dedicated success animation page
    return render_template("payment_success.html", utr=utr_id)
@app.route("/resident-dashboard")
def resident_dashboard():
    if session.get("role") != "resident":
        return redirect(url_for("login"))

    db = get_db()
    # Use buffered=True to handle nested queries safely
    cur = db.cursor(dictionary=True, buffered=True)

    # 1. Get Resident Profile (Personal Info & Rollover Limit)
    cur.execute("""
        SELECT r.id, r.resident_id, r.room_id, r.rollovers_used, rm.room_no, u.name 
        FROM residents r 
        JOIN rooms rm ON r.room_id = rm.id 
        JOIN users u ON r.user_id = u.id
        WHERE r.user_id = %s
    """, (session["user_id"],))
    resident = cur.fetchone()

    if not resident:
        return "Resident profile not found", 404

    # 2. Get Roommates (To show who has paid in split bills)
    cur.execute("""
        SELECT u.name FROM residents r 
        JOIN users u ON r.user_id = u.id 
        WHERE r.room_id = %s
    """, (resident['room_id'],))
    room_roster = [row['name'] for row in cur.fetchall()]

    # 3. Get Complaints and their Chat History
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

    # 4. Get Private Split Bills (Roommate peer-to-peer)
    cur.execute("""
        SELECT id, resident_name, title, amount_per_person, created_at 
        FROM private_splits WHERE room_id = %s ORDER BY created_at DESC
    """, (resident['room_id'],))
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
        s['user_has_paid'] = session.get('name') in paid_list or session.get('name') == s['resident_name']

    # 5. Resident Count for auto-calculation
    cur.execute("SELECT COUNT(*) as count FROM residents WHERE room_id = %s AND user_id IS NOT NULL", (resident['room_id'],))
    resident_count = cur.fetchone()['count']
    
    # 6. OFFICIAL PAYMENTS (UPDATED: Added current_amount and arrear_amount)
    cur.execute("""
        SELECT 
            p.id AS pay_id, 
            p.amount, 
            p.amount_paid, 
            p.current_amount, -- Added for breakdown
            p.arrear_amount,  -- Added for breakdown
            p.fine_amount, 
            p.status, 
            p.created_at, 
            b.title, 
            b.month, 
            b.bill_image, 
            b.created_at AS bill_initiated_at 
        FROM payments p 
        JOIN bills b ON p.bill_id = b.id 
        WHERE p.resident_id = %s 
        AND (p.status != 'rolled_over') 
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
    phone = request.form.get("phone", "")
    owner_id = session["user_id"] 

    db = get_db()
    cur = db.cursor()
    cur.execute("""
        INSERT INTO properties (name, address, phone, owner_id) 
        VALUES (%s, %s, %s, %s)
    """, (name, address, phone, owner_id))
    
    flash(f"Asset {name} deployed to your terminal.", "success")
    return redirect(url_for("owner_dashboard"))
@app.route("/add-resident", methods=["POST"])
def add_resident():
    if session.get("role") != "owner":
        return redirect(url_for("login"))

    email = request.form.get("email")
    room_id = request.form.get("room_id")

    if not email or not room_id:
        flash("Sync Error: Email and Room are required.", "error")
        return redirect(url_for("owner_dashboard"))

    db = get_db()
    cur = db.cursor(dictionary=True)

    try:
        # 1. AUTO-DETECT PROPERTY ID from the room mapping
        cur.execute("SELECT property_id FROM rooms WHERE id = %s", (room_id,))
        room_data = cur.fetchone()
        
        if not room_data:
            flash("Error: Room mapping failed.", "error")
            return redirect(url_for("owner_dashboard"))
            
        property_id = room_data['property_id']

        # 2. Generate Custom Resident ID (e.g., RES001)
        cur.execute("SELECT MAX(CAST(SUBSTRING(resident_id, 4) AS UNSIGNED)) AS last FROM residents")
        result = cur.fetchone()
        last = result["last"] if result and result["last"] is not None else 0
        new_resident_id = f"RES{last + 1:03d}"

        # 3. Insert with the verified unique resident_id string
        cur.execute("""
            INSERT INTO residents (resident_id, email, property_id, room_id, verified)
            VALUES (%s, %s, %s, %s, 0)
        """, (new_resident_id, email, property_id, room_id))
        
        db.commit()
        
        # SUCCESS MESSAGE: Now highlights the unique Resident ID
        flash(f"Resident authorized! System Key Generated: {new_resident_id}", "success")
        
    except Exception as e:
        flash(f"Database Sync Error: {str(e)}", "error")
    
    return redirect(url_for("owner_dashboard"))
@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully", "success")
    return redirect("/")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)