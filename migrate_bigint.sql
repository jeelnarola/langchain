-- Migration to support large Telegram chat IDs
-- Run each line separately in MySQL

ALTER TABLE chat_messages DROP FOREIGN KEY chat_messages_ibfk_1;
ALTER TABLE sessions MODIFY id BIGINT AUTO_INCREMENT;
ALTER TABLE chat_messages MODIFY session_id BIGINT NOT NULL;
ALTER TABLE chat_messages ADD CONSTRAINT chat_messages_ibfk_1 FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE;
