-- Fix the sessions table to add AUTO_INCREMENT
ALTER TABLE sessions MODIFY COLUMN id BIGINT AUTO_INCREMENT;

-- If the above doesn't work, you may need to drop and recreate the table
-- DROP TABLE IF EXISTS sessions;
-- CREATE TABLE sessions (
--     id BIGINT AUTO_INCREMENT PRIMARY KEY,
--     name VARCHAR(255) DEFAULT 'New Chat',
--     created_at DATETIME DEFAULT CURRENT_TIMESTAMP
-- );