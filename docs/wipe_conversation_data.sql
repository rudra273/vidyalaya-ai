-- Wipe conversation + agent-memory data for the channel-architecture cutover.
-- (plan.md §4b) Keeps users, subscriptions, student_profiles, daily_usage.
--
-- DROPs messages (rather than TRUNCATE) so the app's create_all rebuilds it fresh
-- with the widened thread_id column (String(200)) on next startup -- create_all
-- only CREATES missing tables, it never ALTERs an existing one.
--
-- Order:
--   1. Deploy the new code.
--   2. Run this SQL:  psql "$DATABASE_URL" -f docs/wipe_conversation_data.sql
--   3. Restart the app -> create_all recreates `messages` at String(200), empty.

BEGIN;

-- Drop display chat history so it is rebuilt at the new column width.
DROP TABLE IF EXISTS messages;

-- Per-turn usage analytics (keyed by old thread_ids) -- schema unchanged, just clear.
TRUNCATE TABLE usage_events RESTART IDENTITY;

-- LangGraph agent memory (the checkpointer). Old rows are keyed by the old
-- thread_id format, so they must go. checkpoint_migrations is the saver's own
-- version marker and is intentionally left alone.
TRUNCATE TABLE checkpoints, checkpoint_writes, checkpoint_blobs;

COMMIT;

-- NOTE: daily_usage is intentionally NOT wiped (it's quota accounting, not
-- conversation). If you also want to reset quotas, uncomment:
-- TRUNCATE TABLE daily_usage RESTART IDENTITY;
