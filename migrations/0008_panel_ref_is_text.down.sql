-- Only reversible while no numeric panel ref has been stored: those are not
-- UUIDs and the cast would fail. Rows holding one are cleared rather than
-- blocking the rollback -- the account is re-resolved by username on the next
-- request, which is the same path a fresh account takes.

DROP INDEX IF EXISTS idx_users_remnawave_uuid;

UPDATE users SET remnawave_uuid = NULL
    WHERE remnawave_uuid IS NOT NULL
      AND remnawave_uuid !~ '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$';

ALTER TABLE users
    ALTER COLUMN remnawave_uuid TYPE UUID USING remnawave_uuid::uuid;

CREATE INDEX IF NOT EXISTS idx_users_remnawave_uuid ON users (remnawave_uuid)
    WHERE remnawave_uuid IS NOT NULL;
