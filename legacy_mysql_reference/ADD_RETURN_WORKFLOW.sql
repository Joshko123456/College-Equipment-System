USE college_equipment;

-- Run this only if you want to apply the return workflow manually.
-- The Flask app can also add this missing column automatically on startup.
ALTER TABLE borrow_requests ADD COLUMN return_requested_at DATETIME NULL AFTER returned_at;
