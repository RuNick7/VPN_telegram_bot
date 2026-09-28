-- Per-user override for the monthly free LTE allowance.
--
-- `LTE_FREE_GB_PER_CYCLE` sets one number for everyone. This column lets an
-- admin give an individual user a different one -- a compensation gesture, a
-- deal, a tester who needs more -- without changing it globally.
--
-- NULL means "use the global setting", which is deliberately distinct from 0:
-- zero is a real, meaningful override meaning this user gets no free traffic
-- at all. Storing gigabytes rather than bytes because that is the unit an
-- admin types and reads; the conversion happens where the quota is computed.
ALTER TABLE users
    ADD COLUMN lte_free_gb_override INTEGER;

ALTER TABLE users
    ADD CONSTRAINT users_lte_free_gb_override_check
    CHECK (lte_free_gb_override IS NULL OR lte_free_gb_override >= 0);
