DROP INDEX IF EXISTS idx_promo_codes_creator_user;

ALTER TABLE promo_codes
    DROP COLUMN IF EXISTS creator_user_id,
    DROP COLUMN IF EXISTS created_at;
