# X Bookmarks Sync

This repo syncs X (Twitter) bookmarks into Supabase for [aliberkyilmaz.com/bookmarks](https://aliberkyilmaz.com/bookmarks.html).

The target runtime is GitHub Actions. The sync no longer uses `twikit` login with username/password. It now shells out to `twitter-cli`, reads the structured JSON envelope from `twitter bookmarks --json`, and upserts rows into Supabase using `id` as the conflict key.

## How Sync Works

1. GitHub Actions installs Python dependencies, including `twitter-cli`.
2. `scripts/sync.py` runs `twitter bookmarks --json`.
3. The script parses the envelope and maps the exact JSON objects directly to Supabase rows.
4. Derived metadata is added:
   - `tags`
   - `tweetUrl`
   - `syncedAt`
5. Rows are upserted into `public.bookmarks` on `"id"`.

## Required GitHub Secrets

| Secret | Value |
| --- | --- |
| `TWITTER_AUTH_TOKEN` | X `auth_token` cookie value |
| `TWITTER_CT0` | X `ct0` cookie value |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |

The old `X_USERNAME` and `X_PASSWORD` secrets are no longer used.

## Supabase Schema

Apply `supabase/schema.sql` before the first sync. 
It preserves the exact camelCase keys from `twitter-cli`.

## Frontend Follow-up

If `aliberkyilmaz.com/bookmarks` still expects the old snake_case schema (like `tweet_id`, `author_handle`), it must be updated to expect the new twitter-cli shape:
- `id`
- `author.screenName`
- `metrics.likes`
- `createdAt`

## Manual Trigger

Go to **Actions -> Sync X Bookmarks -> Run workflow**.