# AVISHKAR Hackathon Registration Portal

## Description
This is a comprehensive Flask-based platform for managing hackathon registrations, problem statement browsing, team formations, and payment verifications. The system features an admin dashboard for system controls and real-time syncing of registration data to Google Sheets.

## How to run locally

### Prerequisites
- Python 3.8+
- Google Service Account Credentials (`credentials.json`)

### Installation & Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd "AVISHKAR ADMIN"
   ```
2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```
3. Install requriements:
   ```bash
   pip install flask gspread oauth2client werkzeug
   ```
4. Place your Google Sheets `credentials.json` in the root directory.

5. Run the application:
   ```bash
   python app.py
   ```
6. Access the application in your browser at `http://127.0.0.1:5000/`.
