-- Add telegram_chat_id column to sessions table
ALTER TABLE sessions ADD COLUMN telegram_chat_id VARCHAR(50) UNIQUE NULL;

-- Create telegram_users table
CREATE TABLE telegram_users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    chat_id VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);