ALTER TABLE users
    DROP CONSTRAINT IF EXISTS users_lte_free_gb_override_check;

ALTER TABLE users
    DROP COLUMN IF EXISTS lte_free_gb_override;
