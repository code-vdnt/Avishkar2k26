import os
import sys

# Force UTF-8 output so emoji print statements work on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import threading
from werkzeug.utils import secure_filename
import json

app = Flask(__name__)
app.secret_key = 'avishkar2k26_secret_key'

# Upload Configuration
UPLOAD_FOLDER = 'static/uploads/screenshots'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ─── Dataset ───────────────────────────────────────────────────────────────────
with open('problems.json', 'r', encoding='utf-8') as f:
    problems = json.load(f)

registrations = []

# ─── Google Sheets Configuration ───────────────────────────────────────────────
SHEET_URL = "https://docs.google.com/spreadsheets/d/1P4u9zB4VUnWySE-6mWKFg-sSbnXEK4vd18eGIRNNotU/edit?gid=0#gid=0"
SHEET_CONNECTED = False
sheet_obj = None # Main Registration Sheet
payment_sheet_obj = None # Payment Verification Sheet
config_sheet_obj = None # System Config Sheet
announcements_sheet_obj = None # Announcements Sheet
registrations = []
payments_data = []
announcements = []

# Global System Config (Loaded from Sheet or using Defaults)
SYSTEM_CONFIG = {
    "registration_status": "open", # open, pause, closed
    "maintenance_mode": "off",     # on, off
    "max_teams": 500,
    "deadline": "2026-04-15 23:59:59",
    "payment_upi": "avishkar@upi",
    "payment_amount": "500"
}

def init_google_sheets():
    global sheet_obj, payment_sheet_obj, SHEET_CONNECTED, registrations, payments_data
    try:
        # Define API Scopes
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive.file",
            "https://www.googleapis.com/auth/drive"
        ]
        
        # Authenticate using the credentials JSON file
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        client = gspread.authorize(creds)
        
        # Connect to the Spreadsheet
        spreadsheet = client.open_by_url(SHEET_URL)
        
        # ─── Registration Sheet ───
        try:
            sheet_obj = spreadsheet.get_worksheet(0)
        except:
            sheet_obj = spreadsheet.sheet1
            
        # ─── Payments Sheet ───
        try:
            payment_sheet_obj = spreadsheet.worksheet("Payments")
        except gspread.exceptions.WorksheetNotFound:
            payment_sheet_obj = spreadsheet.add_worksheet(title="Payments", rows="100", cols="20")
            headers = ["id", "name", "contact", "utr", "screenshot_url", "status", "timestamp"]
            payment_sheet_obj.append_row(headers)
            print("   ↳ Created 'Payments' worksheet.")

        SHEET_CONNECTED = True
        print("\n✅ Successfully connected to Google Sheets Database!")
        
        # Load Registrations
        all_reg_values = sheet_obj.get_all_values()
        if all_reg_values:
            headers = all_reg_values[0]
            data_rows = all_reg_values[1:]
            registrations.clear()
            for row in data_rows:
                record = dict(zip(headers, row))
                if record.get("team_name", "").strip() and record.get("id", "").strip():
                    registrations.append(record)
            print(f"   ↳ Loaded {len(registrations)} registrations.")

        # Load Payments
        all_payment_values = payment_sheet_obj.get_all_values()
        if all_payment_values:
            headers = all_payment_values[0]
            data_rows = all_payment_values[1:]
            payments_data.clear()
            for row in data_rows:
                record = dict(zip(headers, row))
                if record.get("utr", "").strip() and record.get("name", "").strip():
                    payments_data.append(record)
            print(f"   ↳ Loaded {len(payments_data)} payment records.")

        # ─── Config Sheet ───
        try:
            config_sheet_obj = spreadsheet.worksheet("Config")
        except gspread.exceptions.WorksheetNotFound:
            config_sheet_obj = spreadsheet.add_worksheet(title="Config", rows="100", cols="5")
            config_sheet_obj.append_row(["key", "value"])
            for k, v in SYSTEM_CONFIG.items():
                config_sheet_obj.append_row([k, str(v)])
            print("   ↳ Created 'Config' worksheet.")

        # Load Config from Sheet (Overwrites code defaults)
        config_values = config_sheet_obj.get_all_values()
        if config_values and len(config_values) > 1:
            for row in config_values[1:]:
                if len(row) >= 2:
                    k, v = row[0], row[1]
                    if k in SYSTEM_CONFIG:
                        # Convert to int if needed
                        if k == "max_teams":
                            SYSTEM_CONFIG[k] = int(v)
                        else:
                            SYSTEM_CONFIG[k] = v

        # ─── Announcements Sheet ───
        try:
            announcements_sheet_obj = spreadsheet.worksheet("Announcements")
        except gspread.exceptions.WorksheetNotFound:
            announcements_sheet_obj = spreadsheet.add_worksheet(title="Announcements", rows="100", cols="5")
            announcements_sheet_obj.append_row(["id", "title", "content", "timestamp"])
            print("   ↳ Created 'Announcements' worksheet.")

        # Load Announcements
        announcement_values = announcements_sheet_obj.get_all_values()
        if announcement_values:
            h = announcement_values[0]
            announcements.clear()
            for row in announcement_values[1:]:
                announcements.append(dict(zip(h, row)))
            print(f"   ↳ Loaded {len(announcements)} announcements.")
            
    except Exception as e:
        print(f"\n⚠️ Google Sheets Not Connected: {e}")
        print("   ↳ Falling back to local internal RAM. Ensure 'credentials.json' is present and SHEET_URL is correct.\n")

init_google_sheets()

# ─── Email Configuration ───────────────────────────────────────────────────────
EMAIL_ADDRESS = "your_email@gmail.com"
EMAIL_APP_PASSWORD = "your_16_digit_app_password"  # DO NOT use your normal password, Google requires an 'App Password'
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
ENABLE_EMAILS = False  # Set to True when you want it to send actual emails!

def send_confirmation_email_async(leader_email, team_name, topic, leader_name, problem_title):
    """Sends a professional HTML confirmation email in the background."""
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"✅ Registration Confirmed: AVISHKAR 2k26 ({team_name})"
        msg["From"] = f"AVISHKAR 2k26 <{EMAIL_ADDRESS}>"
        msg["To"] = leader_email

        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; margin: 0; padding: 20px; background: #f8fafc;">
            <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
              <div style="background: linear-gradient(135deg, #0A2540 0%, #0F3460 100%); color: white; padding: 30px 20px; text-align: center;">
                <h1 style="margin: 0; font-size: 28px; letter-spacing: 1px;">⚡ AVISHKAR 2k26 Portal</h1>
                <p style="margin: 8px 0 0 0; font-size: 15px; opacity: 0.9;">Innovation • Technology • Impact</p>
              </div>
              <div style="padding: 40px 30px;">
                <h2 style="color: #0A2540; margin-top: 0; font-size: 22px;">Registration Successful! 🎉</h2>
                <p style="font-size: 16px;">Hi <strong>{leader_name}</strong>,</p>
                <p style="font-size: 16px;">Congratulations! Your team <strong>{team_name}</strong> has successfully secured a slot for the upcoming AVISHKAR 2026 Hackathon.</p>
                
                <div style="background: #f1f5f9; padding: 20px; border-left: 5px solid #FF6A00; margin: 30px 0; border-radius: 6px;">
                  <h3 style="margin-top: 0; color: #0A2540; font-size: 18px;">Your Selected Problem Statement:</h3>
                  <p style="margin: 8px 0 0 0; font-size: 16px;"><strong>ID:</strong> <span style="color: #FF6A00; font-weight: bold;">{topic}</span></p>
                  <p style="margin: 8px 0 0 0; font-size: 16px;"><strong>Title:</strong> {problem_title}</p>
                </div>
                
                <p style="font-size: 16px;">A confirmed copy of your full team registration has been securely uploaded to our database. Please keep an eye on your inbox for upcoming announcements, schedule details, and further instructions from the organizing committee.</p>
                <p style="font-size: 16px; margin-top: 30px;">Best of luck!<br><strong style="color: #0A2540;">The AVISHKAR 2k26 Team</strong></p>
              </div>
              <div style="background: #f1f5f9; text-align: center; padding: 20px; font-size: 13px; color: #64748b; border-top: 1px solid #e2e8f0;">
                © 2026 AVISHKAR Registration. This is an automated confirmation email.
              </div>
            </div>
          </body>
        </html>
        """
        
        msg.attach(MIMEText(html, "html"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_APP_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, leader_email, msg.as_string())
        server.quit()
        print(f"📧 Confirmation email successfully sent to {leader_email}")
    except Exception as e:
        print(f"⚠️ Failed to send email to {leader_email}. Check credentials. Error: {e}")


def update_counts():
    """Update registration counts for each problem statement."""
    for p in problems:
        p["count"] = 0
    for reg in registrations:
        topic_id = reg.get("topic")
        for p in problems:
            if p["id"] == topic_id:
                p["count"] += 1
                break

# ═══════════════════════════════════════════════════════════════════════════════
#  ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    """Homepage - display problems exactly in table format."""
    update_counts()
    
    total_domains = len(set(p['domain'] for p in problems))
    total_capacity = sum(p['max_team_size'] for p in problems)
    teams_registered = len(registrations)
    
    return render_template('index.html', 
                           problems=problems,
                           total_domains=total_domains,
                           total_capacity=total_capacity,
                           teams_registered=teams_registered)

@app.route('/register/<ps_id>')
def register(ps_id):
    """Show form for a specific PS ID."""
    update_counts() # This handles sync_data()
    problem = next((p for p in problems if p["id"] == ps_id), None)
    
    if not problem:
        flash('Invalid Problem Statement ID selected.', 'error')
        return redirect(url_for('index'))
        
    if problem["count"] >= problem["max_team_size"]:
        flash(f'Sorry, {problem["id"]} is already full ({problem["max_team_size"]}/{problem["max_team_size"]} teams).', 'error')
        return redirect(url_for('index'))
        
    remaining = problem["max_team_size"] - problem["count"]
    return render_template('register.html', problem=problem, remaining=remaining)

@app.route('/api/check_duplicates', methods=['POST'])
def check_duplicates():
    """Async API endpoint to check duplicates before opening the preview modal."""
    update_counts() # Ensure latest data before duplicate checks
    data = request.json
    topic = data.get('topic', '').strip()
    team_name = data.get('team_name', '').strip()
    
    incoming_emails = [e.lower() for e in data.get('emails', []) if e.strip()]
    incoming_phones = [p for p in data.get('phones', []) if p.strip()]
    
    if len(set(incoming_emails)) < len(incoming_emails):
        return jsonify({"duplicate": True, "message": "Each team member must have a unique email address."})
        
    if len(set(incoming_phones)) < len(incoming_phones):
        return jsonify({"duplicate": True, "message": "Each team member must have a unique phone number."})
        
    for reg in registrations:
        existing_emails = {
            str(reg.get("email", "")).lower(), 
            str(reg.get("member2_email", "")).lower(), 
            str(reg.get("member3_email", "")).lower(), 
            str(reg.get("member4_email", "")).lower()
        }
        existing_phones = {
            str(reg.get("phone", "")), 
            str(reg.get("member2_phone", "")), 
            str(reg.get("member3_phone", "")), 
            str(reg.get("member4_phone", ""))
        }
        
        dup_emails = set(incoming_emails).intersection(existing_emails)
        dup_phones = set(incoming_phones).intersection(existing_phones)
        
        if dup_emails:
            dup = list(dup_emails)[0]
            return jsonify({"duplicate": True, "message": f'The email "{dup}" is already registered (PS ID: {reg.get("topic", "Unknown")}). Members cannot register for multiple topics.'})
            
        if dup_phones:
            dup = list(dup_phones)[0]
            return jsonify({"duplicate": True, "message": f'The phone number "{dup}" is already registered (PS ID: {reg.get("topic", "Unknown")}). Members cannot register for multiple topics.'})
            
    if any(r.get("team_name", "").lower() == team_name.lower() for r in registrations):
        return jsonify({"duplicate": True, "message": f'The team name "{team_name}" is already taken by another group.'})
        
    return jsonify({"duplicate": False})


@app.route('/submit_registration', methods=['POST'])
def submit_registration():
    """Process the registration form submission."""
    topic       = request.form.get('topic', '').strip()
    team_name   = request.form.get('team_name', '').strip()
    college     = request.form.get('college', '').strip()
    leader_name = request.form.get('leader_name', '').strip()
    email       = request.form.get('email', '').strip()
    phone       = request.form.get('phone', '').strip()
    
    member2_name    = request.form.get('member2_name', '').strip()
    member2_college = request.form.get('member2_college', '').strip()
    member2_email   = request.form.get('member2_email', '').strip()
    member2_phone   = request.form.get('member2_phone', '').strip()

    member3_name    = request.form.get('member3_name', '').strip()
    member3_college = request.form.get('member3_college', '').strip()
    member3_email   = request.form.get('member3_email', '').strip()
    member3_phone   = request.form.get('member3_phone', '').strip()

    member4_name    = request.form.get('member4_name', '').strip()
    member4_college = request.form.get('member4_college', '').strip()
    member4_email   = request.form.get('member4_email', '').strip()
    member4_phone   = request.form.get('member4_phone', '').strip()

    if not all([
        topic, team_name, college, leader_name, email, phone,
        member2_name, member2_college, member2_email, member2_phone,
        member3_name, member3_college, member3_email, member3_phone,
        member4_name, member4_college, member4_email, member4_phone
    ]):
        flash('Please fill in all required fields.', 'error')
        return redirect(url_for('register', ps_id=topic))

    update_counts()
    problem = next((p for p in problems if p["id"] == topic), None)
    if not problem:
        flash('Invalid problem statement.', 'error')
        return redirect(url_for('index'))
        
    if problem["count"] >= problem["max_team_size"]:
        flash(f'Sorry, {topic} just became full. Please choose another topic.', 'error')
        return redirect(url_for('index'))

    # Validate uniqueness WITHIN the submitted team
    incoming_emails_list = [email.lower(), member2_email.lower(), member3_email.lower(), member4_email.lower()]
    incoming_phones_list = [phone, member2_phone, member3_phone, member4_phone]
    
    if len(set(incoming_emails_list)) < 4:
        flash('Each team member must have a unique email address.', 'error')
        return redirect(url_for('register', ps_id=topic))
        
    if len(set(incoming_phones_list)) < 4:
        flash('Each team member must have a unique phone number.', 'error')
        return redirect(url_for('register', ps_id=topic))

    # Check if any member is already registered in ANY topic globally
    for reg in registrations:
        existing_emails = {
            str(reg.get("email", "")).lower(), 
            str(reg.get("member2_email", "")).lower(), 
            str(reg.get("member3_email", "")).lower(), 
            str(reg.get("member4_email", "")).lower()
        }
        existing_phones = {
            str(reg.get("phone", "")), 
            str(reg.get("member2_phone", "")), 
            str(reg.get("member3_phone", "")), 
            str(reg.get("member4_phone", ""))
        }
        
        duplicate_emails = set(incoming_emails_list).intersection(existing_emails)
        duplicate_phones = set(incoming_phones_list).intersection(existing_phones)
        
        if duplicate_emails:
            dup = list(duplicate_emails)[0]
            flash(f'The email "{dup}" is already registered (PS ID: {reg["topic"]}). Members cannot register for multiple topics.', 'error')
            return redirect(url_for('register', ps_id=topic))
            
        if duplicate_phones:
            dup = list(duplicate_phones)[0]
            flash(f'The phone number "{dup}" is already registered (PS ID: {reg["topic"]}). Members cannot register for multiple topics.', 'error')
            return redirect(url_for('register', ps_id=topic))

    # Check duplicates by strictly team name across the entire hackathon
    if any(reg["team_name"].lower() == team_name.lower() for reg in registrations):
        flash(f'The team name "{team_name}" is already taken by another group.', 'error')
        return redirect(url_for('register', ps_id=topic))

    registration_id = max([int(r.get("id", 0)) for r in registrations], default=0) + 1
    new_reg = {
        "id": registration_id,
        "topic": topic,
        "team_name": team_name,
        "leader_name": leader_name,
        "college": college,
        "email": email,
        "phone": phone,
        "member2_name": member2_name,
        "member2_college": member2_college,
        "member2_email": member2_email,
        "member2_phone": member2_phone,
        "member3_name": member3_name,
        "member3_college": member3_college,
        "member3_email": member3_email,
        "member3_phone": member3_phone,
        "member4_name": member4_name,
        "member4_college": member4_college,
        "member4_email": member4_email,
        "member4_phone": member4_phone,
        "member2": member2_name,
        "member3": member3_name,
        "member4": member4_name,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    registrations.append(new_reg)
    
    if SHEET_CONNECTED:
        try:
            row_data = [
                new_reg.get(h, "") for h in [
                    "id", "topic", "team_name", "leader_name", "college", "email", "phone",
                    "member2_name", "member2_college", "member2_email", "member2_phone",
                    "member3_name", "member3_college", "member3_email", "member3_phone",
                    "member4_name", "member4_college", "member4_email", "member4_phone",
                    "member2", "member3", "member4", "timestamp"
                ]
            ]
            sheet_obj.append_row(row_data)
        except Exception as e:
            print("Google Sheets append Error:", e)

    # ─── Send Confirmation Email Asynchronously ───
    if ENABLE_EMAILS:
        problem_title = next((p["title"] for p in problems if p["id"] == topic), "Unknown Topic")
        threading.Thread(
            target=send_confirmation_email_async, 
            args=(email, team_name, topic, leader_name, problem_title)
        ).start()

    update_counts()

    return redirect(url_for('payment', team=team_name, leader=leader_name, contact=email))

# ─── Payment Flow Routes ───

@app.route('/payment')
def payment():
    """Show payment page with QR code."""
    team = request.args.get('team')
    leader = request.args.get('leader')
    contact = request.args.get('contact')
    return render_template('payment.html', team=team, leader=leader, contact=contact)

@app.route('/confirm_payment')
def confirm_payment():
    """Form to submit payment proof."""
    team = request.args.get('team')
    leader = request.args.get('leader')
    contact = request.args.get('contact')
    return render_template('confirm_payment.html', team=team, leader=leader, contact=contact)

@app.route('/submit_payment', methods=['POST'])
def submit_payment():
    """Handle UTR and Screenshot submission."""
    name = request.form.get('name', '').strip()
    contact = request.form.get('contact', '').strip()
    utr = request.form.get('utr', '').strip()
    file = request.files.get('screenshot')

    # Basic Validation
    if not all([name, contact, utr, file]):
        flash('All fields including the screenshot are required.', 'error')
        return redirect(url_for('confirm_payment', team=name, contact=contact))

    if not utr.isdigit() or len(utr) < 10:
        flash('Invalid UTR. It must be numeric and at least 10 digits long.', 'error')
        return redirect(url_for('confirm_payment', team=name, contact=contact))

    # Check Duplicate UTR (Global search across all payment records)
    if any(p.get('utr') == utr for p in payments_data):
        flash(f'UTR "{utr}" has already been submitted. Duplicate submissions are not allowed.', 'error')
        return redirect(url_for('confirm_payment', team=name, contact=contact))

    if file and allowed_file(file.filename):
        filename = secure_filename(f"{utr}_{file.filename}")
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        screenshot_url = url_for('static', filename=f'uploads/screenshots/{filename}')
    else:
        flash('Invalid file type. Please upload an image (PNG, JPG, JPEG).', 'error')
        return redirect(url_for('confirm_payment', team=name, contact=contact))

    # Save to Google Sheets
    new_payment = {
        "id": int(datetime.now().timestamp()), # Simple unique ID
        "name": name,
        "contact": contact,
        "utr": utr,
        "screenshot_url": screenshot_url,
        "status": "pending",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    payments_data.append(new_payment)
    
    if SHEET_CONNECTED:
        try:
            row_data = [new_payment[h] for h in ["id", "name", "contact", "utr", "screenshot_url", "status", "timestamp"]]
            payment_sheet_obj.append_row(row_data)
        except Exception as e:
            print("Google Sheets Payment append Error:", e)

    return redirect(url_for('success', team=name, utr=utr))

@app.route('/success')
def success():
    """Show success page."""
    team = request.args.get('team', 'Your Team')
    topic = request.args.get('topic', '')
    return render_template('success.html', team=team, topic=topic)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'avishkar2026':
            session['logged_in'] = True
            flash('Successfully logged in as admin.', 'success')
            return redirect(url_for('admin'))
        else:
            flash('Invalid username or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

# ─── ADMIN DASHBOARD HELPER FUNCTIONS ───
def get_current_registrations():
    return sorted(registrations, key=lambda x: x["timestamp"], reverse=True)

def get_current_payments():
    return sorted(payments_data, key=lambda x: x["timestamp"], reverse=True)

def get_verified_registrations():
    """Returns only registrations that have an approved payment."""
    approved_emails = {str(p.get("contact", "")).lower().strip() for p in payments_data if p.get("status") == "approved"}
    
    verified = []
    for reg in registrations:
        reg_email = str(reg.get("email", "")).lower().strip()
        if reg_email in approved_emails:
            verified.append(reg)
            
    return sorted(verified, key=lambda x: x["timestamp"], reverse=True)

# ═══════════════════════════════════════════════════════════════════════════════
#  ADMIN NEW API ROUTES (AJAX)
# ═══════════════════════════════════════════════════════════════════════════════

@app.route('/admin/api/update_system', methods=['POST'])
def update_system():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    for k, v in data.items():
        if k in SYSTEM_CONFIG:
            SYSTEM_CONFIG[k] = v
            # Persistent update in sheet
            if SHEET_CONNECTED:
                try:
                    cell = config_sheet_obj.find(k, in_column=1)
                    config_sheet_obj.update_cell(cell.row, 2, str(v))
                except: pass
    return jsonify({"success": True, "config": SYSTEM_CONFIG})

@app.route('/admin/api/announcement', methods=['POST'])
def add_announcement():
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    data = request.json
    new_ann = {
        "id": int(datetime.now().timestamp()),
        "title": data.get('title'),
        "content": data.get('content'),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    announcements.append(new_ann)
    if SHEET_CONNECTED:
        announcements_sheet_obj.append_row([new_ann["id"], new_ann["title"], new_ann["content"], new_ann["timestamp"]])
    return jsonify({"success": True, "announcement": new_ann})

@app.route('/admin/api/delete_announcement/<id>', methods=['POST'])
def delete_announcement(id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    global announcements
    announcements = [a for a in announcements if str(a["id"]) != str(id)]
    if SHEET_CONNECTED:
        try:
            cell = announcements_sheet_obj.find(str(id), in_column=1)
            announcements_sheet_obj.delete_rows(cell.row)
        except: pass
    return jsonify({"success": True})

@app.route('/admin')
def admin():
    """Main Admin Dashboard handling verified registrations and payments."""
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    init_google_sheets()
    update_counts()

    status_filter = request.args.get('status', 'all')
    all_payments = get_current_payments()
    
    if status_filter == 'all':
        filtered_payments = all_payments
    else:
        filtered_payments = [p for p in all_payments if p.get('status') == status_filter]
        
    verified_regs = get_verified_registrations()
    all_regs = get_current_registrations()
    
    stats = {
        "total_registrations": len(all_regs),
        "total_payments": len(all_payments),
        "pending_payments": len([p for p in all_payments if p.get('status') == 'pending']),
        "approved_teams": len(verified_regs)
    }

    return render_template('admin.html', 
                           payments=filtered_payments, 
                           verified_registrations=verified_regs,
                           registrations=all_regs,
                           problems=problems,
                           stats=stats,
                           config=SYSTEM_CONFIG,
                           announcements=announcements,
                           current_filter=status_filter)

@app.route('/admin/payments')
def admin_payments():
    return redirect(url_for('admin'))

@app.route('/delete_registration/<int:reg_id>', methods=['POST'])
def delete_registration(reg_id):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    global registrations
    reg = next((r for r in registrations if str(r["id"]) == str(reg_id)), None)
    if reg:
        registrations = [r for r in registrations if str(r["id"]) != str(reg_id)]
        if SHEET_CONNECTED:
            try:
                cell = sheet_obj.find(str(reg_id), in_column=1)
                sheet_obj.delete_rows(cell.row)
            except: pass
        update_counts()
        return jsonify({"success": True})
    return jsonify({"error": "Not found"}), 404

@app.route('/admin/payment_action/<utr>/<action>', methods=['POST'])
def payment_action(utr, action):
    if not session.get('logged_in'): return jsonify({"error": "Unauthorized"}), 401
    global payments_data
    status = 'approved' if action == 'approve' else ('rejected' if action == 'reject' else 'pending')
    
    found = False
    for p in payments_data:
        if p.get('utr') == utr:
            p['status'] = status
            found = True
            break
            
    if found and SHEET_CONNECTED:
        try:
            cell = payment_sheet_obj.find(utr, in_column=4)
            payment_sheet_obj.update_cell(cell.row, 6, status)
        except: pass
        
    return jsonify({"success": True, "status": status})

if __name__ == '__main__':
    print("\n  🚀  AVISHKAR 2k26 Portal")
    print("  📍  Server initializing...\n")
    print("📍 http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
