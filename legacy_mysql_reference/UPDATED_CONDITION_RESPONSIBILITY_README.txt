UPDATED GOOD / FAIR / DAMAGED REPORTS

Good: included in Condition Report / Cost. Displays the inspection note and PHP
0.00. No damage explanation, admission or cost acceptance is required.
Fair / Damaged: retain the attached system's automatic condition charges.
The inherited defaults are PHP 250 per unit for Fair and PHP 1,000 per unit for
Damaged. Existing equipment-specific rates remain in place. Admin/staff can
change them in Equipment > Edit. Review these settings before operational use.
Cost = configured condition rate multiplied by the transaction quantity.
The inspection condition applies to all units in that transaction.

STUDENT / FACULTY EXPLANATION
Borrow & Return > Condition Report / Cost.
When reporting an issue or replying to an inspection report, explain the affected
serial number, what happened, when, your actions or mistake and observed damage.
Use 20-4,000 characters. State unknown facts honestly.
Check the responsibility acknowledgment to submit. The explanation is saved
separately from the staff inspection note, with its submission time.
Admin/staff can read it. The borrower must then review and explicitly accept
the exact cost. Cost acceptance cannot be submitted before the explanation and
responsibility acknowledgment. Explanations are not silently rewritten; contact
staff for corrections. The existing payment and notification workflows remain.

UPDATE YOUR CURRENT INSTALLATION
Back up your database, stop Python, then replace the application files.
Retain your database settings, existing .secret_key and any newer uploaded photos.
Start MySQL and run py app.py. The two explanation fields are added automatically.
Do not delete your database or re-import schema.sql for an existing installation.
Restart the app and refresh the browser to load the latest forms.

Verification: Python and template checks passed. Flask checks used simulated
DB responses to verify borrower ownership, explanation requirements, cost
acceptance gating, and Good-condition views. Test with your local XAMPP database
before operational use.
