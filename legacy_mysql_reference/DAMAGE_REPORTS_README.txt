FAIR / DAMAGED RETURN RESPONSIBILITY AND AUTOMATIC COSTS

RETURN CONDITIONS
- Good: no responsibility note and no automatic cost.
- Fair: automatically creates a condition/responsibility record and a cost.
- Damaged: automatically creates a condition/responsibility record and a cost.

AUTOMATIC COST SETTINGS
Admin/Staff can set the per-unit Fair Return Cost and Damaged Return Cost for each
equipment type in Equipment Inventory > Add/Edit Equipment. New installations use
defaults of PHP 250.00 for Fair and PHP 1,000.00 for Damaged until staff changes them.
Existing databases receive these two fields automatically when the Flask app starts.

WHEN A RETURN IS INSPECTED
For Fair or Damaged, the system automatically creates the condition note, calculates
configured cost x returned quantity, stores the assessment, and notifies the borrower.
The borrower opens Condition Report / Cost and acknowledges responsibility and the cost.
Staff may revise the automatic amount if the actual repair/replacement situation requires
a different charge. Revising the amount requires a new borrower cost acknowledgment.

For Good, the transaction simply records Good and completes the return. The system does
not create the responsibility/cost workflow and the Condition Report / Cost link is not
shown after the return.

PAYMENTS
After receiving full payment offline, Admin/Staff can enter the receipt/reference and
mark the charge paid. The system records payment only; it does not process online money.

UPDATE EXISTING INSTALLATION
Back up the database, replace the application files, retain database settings and
.secret_key, then run: py app.py
The app safely adds fair_cost and damage_cost if they are missing. Do not delete or
re-import the existing database. AUTO_CONDITION_COSTS.sql is included only for users
who prefer to apply the two new columns manually.
