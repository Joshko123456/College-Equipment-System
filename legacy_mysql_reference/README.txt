COLLEGE EQUIPMENT BORROWING AND RETURN MANAGEMENT SYSTEM
BCC-THEMED - STABLE AUTHENTICATION BUILD

TECHNOLOGY
- Frontend: HTML, CSS, JavaScript
- Backend: Python Flask
- Database: MySQL / phpMyAdmin (XAMPP)

FIRST-TIME INSTALLATION ONLY
1. Start MySQL in XAMPP.
2. Import schema.sql into phpMyAdmin.
3. In the project folder run:
   python -m pip install -r requirements.txt
   python app.py
4. Create the first administrator at:
   http://127.0.0.1:5000/setup

EXISTING INSTALLATION / UPDATE
IMPORTANT: DO NOT DELETE your college_equipment database.
IMPORTANT: DO NOT re-import schema.sql if your database already contains records.
Just replace the project files and run python app.py.
The application creates only missing support tables and preserves existing data.

LOGIN PAGES
Student: http://127.0.0.1:5000/student/login
Admin/Staff: http://127.0.0.1:5000/admin/login

ADMIN RECOVERY
- If an existing Administrator record is present but inactive, the Admin Login page shows a recovery link.
- Recovery uses the same existing Admin record and sets a new password; it does not create a duplicate.
- If there is no Administrator row at all, /setup creates a new administrator without changing existing students, equipment, or transactions.

CHECKING ADMIN RECORDS IN PHPMYADMIN
Run CHECK_ADMIN_RECORDS.sql from phpMyAdmin > college_equipment > SQL.

STUDENT ACCOUNT FLOW
1. Admin creates the official Student Record.
2. Student opens /student/register.
3. Student enters the Student ID and creates their own password.
4. Student signs in at /student/login.

SESSION DESIGN
- Admin uses a dedicated Admin browser session.
- Student sessions do not use or overwrite the Admin session.
- Each Student login gets its own path-scoped secure session record.
- Multiple students can remain signed in independently in separate tabs/session URLs.
- Private pages disable browser caching.


Update: Real equipment images were added for the default seeded items and category fallback images.
