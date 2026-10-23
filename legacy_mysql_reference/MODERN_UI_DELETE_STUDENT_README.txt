MODERN UI + STUDENT DELETE UPDATE
=================================

New features:
1. Admin Student Records now includes a Delete button for every active student.
2. If a student has no borrowing/return history, their student account and registry record are deleted.
3. If borrowing/return history exists, the account is deactivated and the student is removed from the active Student Records list while transaction history is preserved for reports.
4. Active student login sessions are revoked when the student is removed.
5. A confirmation dialog prevents accidental deletion.
6. Student Records now includes search, modern status badges, avatars, responsive styling, and summary cards.
7. Create Personnel Account has a cleaner modern two-section layout.
8. Student personal account activation was redesigned and includes a password-strength indicator.
9. General UI styling was refreshed across navigation, panels, buttons, forms, cards, modals, light mode, dark mode, and mobile layouts.

DATABASE
No new table or database migration is required. This update uses the existing users, student_records, auth_sessions, notifications, and borrow_requests tables.

IMPORTANT
Back up your database before replacing an existing system folder.
