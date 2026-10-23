USE college_equipment;
SELECT id, school_id, full_name, email, role, active, created_at
FROM users
WHERE role IN ('admin','staff')
ORDER BY id;
