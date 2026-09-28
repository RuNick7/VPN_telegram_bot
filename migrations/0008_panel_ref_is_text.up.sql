-- `remnawave_uuid` holds whatever the panel calls the account, which is not
-- always a UUID.
--
-- Newer Remnawave dropped `uuid` from user records and identifies accounts by
-- a numeric `id`. The column was declared UUID, so storing "46" failed with
-- `invalid input syntax for type uuid` -- the write was logged as a warning and
-- swallowed, which left the account unfindable: every later request looked it
-- up, missed, tried to create it again, and was told the name was taken. A
-- customer paid and got nothing, because the payment webhook hit the same wall.
--
-- TEXT rather than a second column: there is one identifier per account, only
-- its spelling differs by panel version, and the code already tells the two
-- apart by whether the value parses as an integer. The name stays as it is --
-- renaming it would touch both bots and the website for no behavioural gain,
-- and every existing row still holds a real UUID.
--
-- The USING clause keeps those rows readable; the cast is lossless in this
-- direction and the index is rebuilt to match.

DROP INDEX IF EXISTS idx_users_remnawave_uuid;

ALTER TABLE users
    ALTER COLUMN remnawave_uuid TYPE TEXT USING remnawave_uuid::text;

CREATE INDEX IF NOT EXISTS idx_users_remnawave_uuid ON users (remnawave_uuid)
    WHERE remnawave_uuid IS NOT NULL;
