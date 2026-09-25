DROP INDEX IF EXISTS idx_promo_usage_code_user;
DROP INDEX IF EXISTS idx_promo_usage_user_id;

-- Rows owned by a website account have no telegram_id to restore, so they
-- would violate the constraint being put back. They are removed, which frees
-- those codes again -- acceptable only because this is a rollback.
DELETE FROM promo_usage WHERE telegram_id IS NULL;

ALTER TABLE promo_usage ALTER COLUMN telegram_id SET NOT NULL;
ALTER TABLE promo_usage
    ADD CONSTRAINT promo_usage_telegram_id_fkey
    FOREIGN KEY (telegram_id) REFERENCES users (telegram_id);

ALTER TABLE promo_usage DROP COLUMN IF EXISTS user_id;
