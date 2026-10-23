BCC EQUIPMENT SERVICES - WORKING NOTIFICATION SYSTEM
====================================================

What was added/fixed
--------------------
1. Student submits a borrowing request
   - Every active Administrator and Staff account receives a notification.
   - The student receives a submission confirmation notification.

2. Administrator/Staff approves or rejects a request
   - The student receives an approval/rejection notification.
   - Approved notifications include the borrow date and due date.

3. Equipment is released/borrowed
   - The student receives a notification reminding them of the return due date.

4. Due-date reminders
   - Student receives a reminder one day before the due date.
   - Student receives another reminder on the due date.
   - Once overdue, the student receives an overdue alert.
   - Admin and Staff also receive the overdue equipment alert.

5. Equipment is returned
   - Student receives a return confirmation and recorded condition.
   - All active Admin and Staff accounts receive a return notification.

6. Live notification experience
   - Unread count appears on the Notifications menu and bell.
   - The browser checks for new notifications every 10 seconds while signed in.
   - New notifications show a toast popup and play a two-tone sound.
   - Sound can be switched on/off from the top bar or Notification Center.

Browser sound note
------------------
Modern browsers may block sound before the first click/tap/keyboard interaction on a page.
The system automatically unlocks notification audio as soon as the signed-in user interacts
with the page. After that, incoming notifications play normally while the page is open.

Database
--------
No new database table is required. The existing notifications table is used, so this update
can be applied to the current database without deleting users, equipment, or transaction history.
