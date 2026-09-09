ALTER TABLE promo_usage DROP CONSTRAINT IF EXISTS promo_usage_user_id_fkey;
ALTER TABLE promo_usage
    ADD CONSTRAINT promo_usage_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users (id);
