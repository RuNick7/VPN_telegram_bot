-- Which low-traffic warning a user has already been sent this cycle.
--
-- The traffic monitor runs every few minutes, so without remembering this it
-- would re-send "you have under 500 MB left" on every pass until the user
-- either topped up or ran out entirely.
--
-- Stores the threshold in megabytes (500, 150), or 0 for "nothing sent". Kept
-- as the threshold rather than a boolean so crossing 500 and later 150 sends
-- two distinct warnings, while re-crossing the same one sends nothing. Reset
-- to 0 when the cycle rolls over or the balance recovers.
ALTER TABLE users
    ADD COLUMN lte_low_traffic_notified_mb INTEGER NOT NULL DEFAULT 0;
