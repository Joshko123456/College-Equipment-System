BCC COLLEGE EQUIPMENT BORROWING & RETURN SYSTEM
Return Workflow + Home Menu Update

STUDENT RETURN WORKFLOW
1. Admin/Staff approves and releases an equipment request.
2. On the request due date (or after it is overdue), the Student's My Borrowing page shows a Return Equipment button.
3. The student clicks Return Equipment. This records return_requested_at but DOES NOT increase inventory yet.
4. Admin and Staff receive an in-app notification and live notification sound that the student is returning the item.
5. The student brings the physical equipment to Admin/Staff.
6. Admin/Staff inspects the equipment and records Good, Fair, or Damaged, with optional notes.
7. Only after inspection is completed does the system increase available inventory and mark the request Returned.
8. The student receives a condition-specific notification and sound alert.

DUE-DATE NOTIFICATIONS
- 1 day before due date: Student reminder.
- Due date: Student notification says the Return Equipment button is available.
- Overdue: Student and Admin/Staff receive overdue notifications.
- Once the student submits the return, duplicate due/overdue reminders stop while inspection is pending.

HOME MENU NAVIGATION
- Student, Admin, and Staff use the same Home-icon menu launcher.
- The full main menu is hidden by default.
- Click the Home icon in the upper-left to open/close the feature menu.
- This works on desktop and mobile.

DATABASE
- New column: borrow_requests.return_requested_at DATETIME NULL
- The application automatically creates this missing column on startup.
- ADD_RETURN_WORKFLOW.sql is included for optional manual migration.
