-- The bot asks once whether the customer would follow the news channel,
-- before the first menu it shows them. Not a gate: «Я подписался» lets anyone
-- through, subscribed or not. The flag only stops the question repeating.
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS channel_prompt_shown BOOLEAN NOT NULL DEFAULT FALSE;
