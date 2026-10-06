-- Schema + sample data for the Lost & Found FastAPI services.
-- Executed automatically by the MySQL container on first start
-- (mounted into /docker-entrypoint-initdb.d).
-- Schema was reconstructed from the SQL used in the three services.

CREATE DATABASE IF NOT EXISTS college_lost_found;
USE college_lost_found;

CREATE TABLE IF NOT EXISTS users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    fullname    VARCHAR(100) NOT NULL,
    usn         VARCHAR(30)  NOT NULL UNIQUE,
    department  VARCHAR(100) NOT NULL,
    email       VARCHAR(120) NOT NULL UNIQUE,
    mobile      VARCHAR(15)  NOT NULL,
    password    VARCHAR(255) NOT NULL,
    role        VARCHAR(20)  NOT NULL DEFAULT 'student',
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS items (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    item_name       VARCHAR(100) NOT NULL,
    description     TEXT,
    location        VARCHAR(150) NOT NULL,
    reporter_name   VARCHAR(100) NOT NULL,
    reporter_phone  VARCHAR(15)  NOT NULL,
    report_type     VARCHAR(10)  NOT NULL,           -- 'lost' or 'found'
    status          VARCHAR(20)  NOT NULL DEFAULT 'open',
    claimant_name   VARCHAR(100) NULL,
    claimant_phone  VARCHAR(15)  NULL,
    created_at      TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO users (fullname, usn, department, email, mobile, password, role) VALUES
 ('Asha Rao',     '1XX21CS001', 'Computer Science', 'asha@example.edu',  '9000000001', 'sample-not-a-real-password', 'student'),
 ('Ravi Kumar',   '1XX21EC014', 'Electronics',      'ravi@example.edu',  '9000000002', 'sample-not-a-real-password', 'student'),
 ('Admin Office', 'ADMIN001',   'Administration',   'admin@example.edu', '9000000003', 'sample-not-a-real-password', 'admin');

INSERT INTO items (item_name, description, location, reporter_name, reporter_phone, report_type, status, claimant_name, claimant_phone) VALUES
 ('Black Wallet',   'Leather wallet with ID card',  'Library',        'Asha Rao',   '9000000001', 'found', 'returned', 'Ravi Kumar', '9000000002'),
 ('Blue Umbrella',  'Folding umbrella',             'Main Canteen',   'Ravi Kumar', '9000000002', 'lost',  'open',     NULL,         NULL),
 ('Scientific Calculator', 'Casio fx-991EX',        'Exam Hall 3',    'Asha Rao',   '9000000001', 'found', 'claimed',  'Ravi Kumar', '9000000002'),
 ('Water Bottle',   'Steel bottle, green cap',      'Sports Ground',  'Admin Office','9000000003','found', 'open',     NULL,         NULL);
