CREATE DATABASE IF NOT EXISTS college_equipment CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE college_equipment;
CREATE TABLE IF NOT EXISTS users (
 id INT AUTO_INCREMENT PRIMARY KEY, school_id VARCHAR(30) UNIQUE NOT NULL, full_name VARCHAR(120) NOT NULL,
 email VARCHAR(120) UNIQUE, password_hash VARCHAR(255) NULL, role ENUM('admin','staff','student','faculty') NOT NULL DEFAULT 'student',
 department VARCHAR(100), active BOOLEAN DEFAULT TRUE, activation_required BOOLEAN NOT NULL DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



CREATE TABLE IF NOT EXISTS auth_sessions (
 id BIGINT AUTO_INCREMENT PRIMARY KEY,
 session_scope VARCHAR(64) UNIQUE NOT NULL,
 token_hash CHAR(64) UNIQUE NOT NULL,
 user_id INT NOT NULL,
 role ENUM('student','faculty') NOT NULL DEFAULT 'student',
 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 last_seen DATETIME NULL,
 expires_at DATETIME NOT NULL,
 revoked BOOLEAN DEFAULT FALSE,
 INDEX idx_auth_user (user_id),
 INDEX idx_auth_expiry (expires_at),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);

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
);
CREATE TABLE IF NOT EXISTS categories (id INT AUTO_INCREMENT PRIMARY KEY, name VARCHAR(80) UNIQUE NOT NULL, description VARCHAR(255));
CREATE TABLE IF NOT EXISTS equipment (
 id INT AUTO_INCREMENT PRIMARY KEY, asset_code VARCHAR(40) UNIQUE NOT NULL, serial_number VARCHAR(100) UNIQUE NOT NULL, name VARCHAR(120) NOT NULL, model VARCHAR(120) NOT NULL, category_id INT,
 description TEXT, total_qty INT NOT NULL DEFAULT 1, available_qty INT NOT NULL DEFAULT 1,
 condition_status ENUM('Good','Fair','For Repair','Damaged') DEFAULT 'Good', location VARCHAR(120), image_filename VARCHAR(255) NULL,
 fair_cost DECIMAL(10,2) NOT NULL DEFAULT 250.00, damage_cost DECIMAL(10,2) NOT NULL DEFAULT 1000.00, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(category_id) REFERENCES categories(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS borrow_requests (
 id INT AUTO_INCREMENT PRIMARY KEY, borrower_id INT NOT NULL, equipment_id INT NOT NULL, quantity INT NOT NULL DEFAULT 1,
 purpose VARCHAR(255) NOT NULL, borrow_date DATE NOT NULL, due_date DATE NOT NULL,
 status ENUM('Pending','Approved','Rejected','Released','Returned','Overdue','Cancelled') DEFAULT 'Pending',
 reviewed_by INT NULL, reviewed_at DATETIME NULL, released_at DATETIME NULL, returned_at DATETIME NULL, return_requested_at DATETIME NULL, return_condition VARCHAR(50), remarks VARCHAR(255), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(borrower_id) REFERENCES users(id), FOREIGN KEY(equipment_id) REFERENCES equipment(id), FOREIGN KEY(reviewed_by) REFERENCES users(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS notifications (id INT AUTO_INCREMENT PRIMARY KEY, user_id INT NOT NULL, message VARCHAR(255) NOT NULL, is_read BOOLEAN DEFAULT FALSE, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE);
INSERT IGNORE INTO categories(name,description) VALUES ('Computers','Laptops and computer equipment'),('Audio Visual','Projectors, speakers and AV devices'),('Laboratory','Laboratory tools and devices'),('Sports','Sports equipment'),('Electronics','Electronic devices and accessories');
INSERT IGNORE INTO equipment(asset_code,serial_number,name,model,category_id,description,total_qty,available_qty,condition_status,location) VALUES
('CE-001','LEGACY-1','Laptop','Lenovo ThinkPad E14',1,'Laptop for academic activities',10,10,'Good','IT Laboratory'),
('CE-002','LEGACY-2','LCD Projector','Epson EB-X06',2,'Projector for classes and presentations',6,6,'Good','AV Room'),
('CE-003','LEGACY-3','Portable Speaker','JBL PartyBox Encore Essential',2,'Portable classroom speaker',4,4,'Good','AV Room'),
('CE-004','LEGACY-4','Digital Multimeter','UNI-T UT33D+',5,'Digital testing meter',12,12,'Good','Electronics Laboratory'),
('CE-005','LEGACY-5','Extension Cord','Omni WEE-003',5,'Heavy duty extension cord',15,15,'Good','Stock Room');
