DROP TABLE IF EXISTS email_verifications;

ALTER TABLE users
    DROP COLUMN IF EXISTS trial_signup_granted,
    DROP COLUMN IF EXISTS trial_link_granted,
    DROP COLUMN IF EXISTS bonus_offer_dismissed,
    DROP COLUMN IF EXISTS bonus_offer_shown_in_bot;
