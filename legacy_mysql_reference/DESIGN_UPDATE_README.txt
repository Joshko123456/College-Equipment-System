BCC EQUIPMENT BORROWING & RETURN SYSTEM - DESIGN UPDATE

WHAT CHANGED
- Redesigned Student Login with a two-panel college portal layout.
- Redesigned Admin/Staff Login with a distinct administration theme.
- Added password show/hide controls.
- Redesigned Student Account Activation page.
- Added richer dashboard hero, statistic cards, quick actions and responsive tables.
- Improved equipment cards with availability bars and cleaner status badges.
- Improved Student Records, Personnel Accounts, Borrow/Return, Reports and Notifications pages.
- Added responsive mobile sidebar/navigation.
- Added better modal forms, alerts, hover effects, empty states and print styling.
- All existing Flask/MySQL functionality is retained.

LOGO
The included file static/images/bcc-mark.svg is a CUSTOM PLACEHOLDER mark, not an official college seal.
To use an official school logo, replace bcc-mark.svg with an approved image and update the image filename in the templates if needed.
Do not treat the placeholder as an official logo.

LOGIN URLS
Student: http://127.0.0.1:5000/student/login
Admin/Staff: http://127.0.0.1:5000/admin/login
Initial Admin Setup: http://127.0.0.1:5000/setup

EQUIPMENT IMAGE UPDATE
- Every equipment card now displays a local image.
- Built-in images are included for the default Laptop, LCD Projector, Portable Speaker, Digital Multimeter, and Extension Cord records.
- Category fallback images are used for other existing equipment.
- Admin/Staff can upload or replace an equipment image in Add Equipment / Edit Equipment.
- Accepted formats: PNG, JPG/JPEG, WEBP.
- Existing login and borrowing records are preserved. The app safely adds only the nullable `image_filename` column when missing.
