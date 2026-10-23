COLLEGE EQUIPMENT BORROWING & RETURN MANAGEMENT SYSTEM
STABLE LOGIN / RECORD-PRESERVING UPDATE

IMPORTANT FOR EXISTING INSTALLATIONS
------------------------------------
Do NOT delete the college_equipment database.
Do NOT re-import schema.sql when you already have student/equipment/borrowing records.
The app now creates only missing support tables automatically.

LOGIN URLS
----------
Student: http://127.0.0.1:5000/student/login
Admin/Staff: http://127.0.0.1:5000/admin/login
First Admin setup (only if there is no admin row): http://127.0.0.1:5000/setup
Admin recovery (only if an old admin exists but is inactive): http://127.0.0.1:5000/admin/recover

WHAT WAS FIXED
--------------
1. Admin session is no longer automatically injected into Student login pages.
2. Student login/activation does not use the Admin Flask session for messages.
3. Admin and Student can be used in the same browser without one UI replacing the other.
4. Multiple student sessions can remain independent using separate path-scoped secure session records.
5. Existing admin rows are never overwritten by setup.
6. If an old admin is inactive, /admin/recover reactivates that same database row.
7. If no admin row exists, /setup can create a replacement without changing other records.
8. No database reset is required for this update.

TO CHECK OLD ADMIN RECORDS
--------------------------
Open phpMyAdmin > college_equipment > SQL and run CHECK_ADMIN_RECORDS.sql.
If the old Admin appears with active=0, use /admin/recover.
If no Admin row appears at all, use /setup to create a replacement Admin.
