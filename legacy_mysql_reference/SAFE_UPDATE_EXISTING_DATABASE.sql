-- SAFE UPDATE FOR AN EXISTING college_equipment DATABASE
-- This script DOES NOT DROP tables and DOES NOT DELETE existing records.
USE college_equipment;

CREATE TABLE IF NOT EXISTS auth_sessions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 session_scope VARCHAR(64) UNIQUE NOT NULL,
 token_hash CHAR(64) UNIQUE NOT NULL,
 user_id INT NOT NULL,
 role ENUM('student') NOT NULL DEFAULT 'student',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_seen DATETIME NULL,
 expires_at DATETIME NOT NULL,
 revoked BOOLEAN DEFAULT FALSE,
 INDEX idx_auth_user (user_id),
 INDEX idx_auth_expiry (expires_at),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS student_records (
 id INT AUTO_INCREMENT PRIMARY KEY,
 student_id VARCHAR(30) UNIQUE NOT NULL,
 full_name VARCHAR(120) NOT NULL,
 email VARCHAR(120),
 program VARCHAR(120),
 year_level VARCHAR(30),
 section VARCHAR(60),
 user_id INT UNIQUE NULL,
 active BOOLEAN DEFAULT TRUE,
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 registered_at DATETIME NULL,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;


-- Optional equipment photo support (safe: adds one nullable column only if missing).
SET @has_equipment_image := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='equipment' AND COLUMN_NAME='image_filename');
SET @equipment_image_sql := IF(@has_equipment_image=0, 'ALTER TABLE equipment ADD COLUMN image_filename VARCHAR(255) NULL AFTER location', 'SELECT 1');
PREPARE stmt_equipment_image FROM @equipment_image_sql;
EXECUTE stmt_equipment_image;
DEALLOCATE PREPARE stmt_equipment_image;


-- Student-initiated return workflow support.
-- If this column already exists, skip this statement.
ALTER TABLE borrow_requests ADD COLUMN return_requested_at DATETIME NULL AFTER returned_at;
