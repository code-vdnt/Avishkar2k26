# AVISHKAR 2k26 Portal - Full Project Documentation

## 🚀 Overview
The **AVISHKAR 2k26 Registration Portal** is a production-ready Flask web application designed to handle high-traffic student registrations for a technical event. It integrates deeply with **Google Sheets** as a real-time database, providing a low-cost, high-reliability storage backend for team data and payment verification.

The application features a modern, Single-Page Application (SPA) style **Admin Dashboard** for event organizers to monitor stats, verify payments, and manage registrations seamlessly.

---

## 🛠️ Technology Stack
- **Backend:** Python (Flask + Werkzeug)
- **Database:** Google Sheets API (via `gspread`)
- **Frontend:** HTML5, CSS3 (Vanilla + Custom Animations), Bootstrap 5, JavaScript (ES6 SPA logic)
- **Emailing:** SMTP Integration for automated registration receipts
- **Environment:** Windows-optimized (Waitress Support, UTF-8 output handling)

---

## 📂 Project Structure
```text
AVISHKAR ADMIN/
├── app.py                # Main Flask logic (Routes, GSheet Sync, Actions)
├── credentials.json       # Google Service Account credentials (KEEP SECURE)
├── static/                # Assets
│   ├── style.css          # Primary design tokens and UI styles
│   ├── hero-bg.png        # Welcome landing illustration
│   ├── qr_code.png        # Payment gateway reference
│   └── uploads/           # User-submitted payment proof screenshots
├── templates/             # HTML View Components
│   ├── admin.html         # Unified SPA-style Dashboard
│   ├── index.html         # Primary registration entry point
│   ├── register.html      # Problem-statement specific registration flow
│   ├── payment.html       # UTR and Proof submission form
│   ├── login.html         # Secure admin authentication
│   ├── success.html       # Completion feedback
│   └── (others)           # Flow-specific redirects (confirm_payment, etc.)
└── fetch.py/output*      # [Temporary] Debug & validation artifacts
```

---

## 🔥 Key Features

### 1. Unified Admin Dashboard (`/admin`)
- **Dashboard Overview:** Displays real-time stats (Total Regs, Total Payments, Pending, Approved) fetched directly from the sheet.
- **Section-Based Navigation:** Custom SPA logic allows toggling between Dashboard, Approved Teams, Payment Verification, and Master Registration List without page reloads.
- **Payment Verification:** Organizers can approve/reject payments. Approvals instantly synchronize with the Google Sheet and move teams to the "Verified" list.
- **Registration Filtering:** Built-in search engine and dropdown filters (by Problem Statement ID) for the master list.

### 2. Google Sheets Integration
- Uses **gspread** for bidirectional communication.
- Automated row search (via UTR) and status updates.
- Real-time caching for high performance.

### 3. Student Workflow
- **Registration:** Multi-member team validation and problem statement selection.
- **Payment Flow:** Seamless transition from registration to payment collection.
- **Proof Submission:** Image upload handling for payment screenshots with automatic renaming and unique ID tagging.

---

## ⚙️ Core Logic (`app.py`)
- `get_current_registrations()`: Retrieves the master list from the sheet.
- `get_verified_registrations()`: Filters for teams with successful payment statuses.
- `admin()`: The core dashboard route serving the consolidated view.
- `payment_action()`: Atomic update logic for moving a team from Pending to Approved/Rejected.

---

## 🏃 Running the Project
1. **Dependencies:**
   ```bash
   pip install flask gspread oauth2client requests
   ```
2. **Setup Credentials:**
   Ensure `credentials.json` is in the root directory and your Google Sheet is shared with the Service Account email.
3. **Run Server:**
   ```bash
   python app.py
   ```
   *Note: Access the admin panel at `http://127.0.0.1:5000/admin`*

---

## 🔒 Security
- **Protected Routes:** All `/admin` endpoints require a secure session token.
- **Action Validation:** Destructive actions like deletion require explicit confirmation.
- **Dynamic Routing:** Redirects optimized for post-action status (e.g., returning to specific UI sections via URL hashes).
