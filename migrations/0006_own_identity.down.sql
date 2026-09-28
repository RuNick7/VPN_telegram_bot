DROP TABLE IF EXISTS account_link_tokens;

ALTER TABLE users DROP COLUMN IF EXISTS remnawave_username;

DROP INDEX IF EXISTS idx_users_remnawave_uuid;
DROP INDEX IF EXISTS idx_users_merged_into;
