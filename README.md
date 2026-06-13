# PG-Sync 🏠🔄

PG-Sync is a centralized, full-stack digital management system designed to streamline and automate Paying Guest (PG) accommodations. It replaces inefficient manual tracking with robust automated billing, role-based dashboards, and image processing for expense tracking.

🌐 **Live Demo:** [https://pg-sync-production.up.railway.app](https://pg-sync-production.up.railway.app)

---

## 🚀 Key Features

* **Role-Based Authentication:** Secure, separate dashboards and workflows for both PG Admins and Residents.
* **Automated Monthly Billing:** Built-in smart billing logic that handles recurring rent generation and tracks individual user arrears automatically.
* **Smart Utility OCR Tracking:** Utilizes computer vision (**OpenCV** and **Tesseract OCR**) to scan physical utility bills, instantly extracting amounts and bill details.
* **Room-Based Expense Splitting:** Dynamically calculates and distributes shared room expenses or utility bills among roommates.
* **Complaint Ticketing System:** A structured digital desk for residents to lodge complaints, track resolution status, and communicate with administration.

---

## 🛠️ Tech Stack

* **Backend:** Python (Flask)
* **Database:** MySQL
* **Frontend:** HTML5, CSS3, JavaScript
* **Libraries & Tools:** OpenCV, PyTesseract (OCR)
* **Deployment:** Railway

---

## ⚙️ Installation & Local Setup

### Prerequisites
Ensure you have the following installed on your local machine:
* Python 3.8+
* MySQL Server
* Tesseract OCR engine (required for bill scanning features)

### 1. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/PG-Sync.git](https://github.com/YOUR_USERNAME/PG-Sync.git)
cd PG-Sync2. Set Up a Virtual Environment
Bash
# Create environment
python -m venv venv

# Activate environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate
3. Install Dependencies
Bash
pip install -r requirements.txt
4. Configure Environment Variables
Create a .env file in the root directory and add your database configuration details:

Code snippet
DB_HOST=localhost
DB_USER=your_mysql_user
DB_PASSWORD=your_mysql_password
DB_NAME=pg_sync
SECRET_KEY=your_secret_key
5. Run the Application
The app includes an automatic database initialization script. When you run the application for the first time, it will automatically connect to your MySQL instance
This project is open-source and available under the MIT License.and execute CREATE TABLE IF NOT EXISTS queries to set up your schema.
