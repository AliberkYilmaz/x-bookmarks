# X Bookmarks Sync

This repo syncs X (Twitter) bookmarks into Supabase for [aliberkyilmaz.com/bookmarks](https://aliberkyilmaz.com/bookmarks.html).

The target runtime is GitHub Actions. The sync no longer uses `twikit` login with username/password. It now shells out to `twitter-cli`, reads the structured JSON envelope from `twitter bookmarks --json`, and upserts rows into Supabase using `id` as the conflict key.

## How Sync Works

1. GitHub Actions installs Python dependencies, including `twitter-cli`.
2. `scripts/sync.py` runs `twitter bookmarks --json`.
3. The script validates the CLI envelope:
   - `success.ok`
   - `success.schema_version`
   - `success.data`
4. Each bookmark is normalized into the new Supabase row model.
5. Derived metadata is added:
   - `tags`
   - `tweet_url`
   - `synced_at`
   - `created_at_ts`
6. Rows are upserted into `public.bookmarks` on `id`.

If `twitter-cli` returns empty stdout, malformed JSON, or a malformed envelope, the workflow fails with a clear error.

## Required GitHub Secrets

| Secret | Value |
| --- | --- |
| `TWITTER_AUTH_TOKEN` | X auth token cookie value |
| `TWITTER_CT0` | X `ct0` cookie value |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |

The old `X_USERNAME` and `X_PASSWORD` secrets are no longer used.

## Supabase Schema

Apply [supabase/schema.sql](/private/tmp/x-bookmarks/supabase/schema.sql) before the first sync with the new fetch layer.

The new table keeps the main twitter-cli payload shape directly in the row:

- `id`
- `text`
- `author` `jsonb`
- `metrics` `jsonb`
- `created_at`
- `media` `jsonb`
- `urls` `jsonb`
- `is_retweet`
- `retweeted_by`
- `lang`
- `score`
- `article_title`
- `article_text`
- `quoted_tweet` `jsonb`

Derived fields kept in the table:

- `tags`
- `tweet_url`
- `synced_at`
- `created_at_ts`

This schema replaces the old twikit-shaped table. The SQL file drops and recreates `public.bookmarks`, so run the sync again after applying it.

## Data Model Change

The old model was a flattened custom schema with fields such as:

- `tweet_id`
- `author_handle`
- `author_avatar_url`
- `images`
- `posted_at`
- `like_count`
- `retweet_count`
- `reply_count`

The new model stores the twitter-cli structure instead:

- `author.screenName` lives inside `author`
- counts live inside `metrics`
- media stays in `media`
- quoted tweet data stays in `quoted_tweet`
- the primary key is `id`

## Frontend Follow-up

If `aliberkyilmaz.com/bookmarks` still expects the old schema, it will need a follow-up update. The most likely changes are:

- switch from `tweet_id` to `id`
- switch from flat author fields to `author.name`, `author.screenName`, and `author.profileImageUrl`
- switch from `images` to `media`
- switch from `posted_at` to `created_at` or `created_at_ts`
- switch from `like_count` / `retweet_count` / `reply_count` to `metrics.likes`, `metrics.retweets`, and `metrics.replies`
- handle `quoted_tweet` as nested JSON instead of the old custom object

## Manual Trigger

Go to `Actions -> Sync X Bookmarks -> Run workflow`, or trigger it via the GitHub API:

```bash
curl -X POST \
  -H "Authorization: token YOUR_GITHUB_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/AliberkYilmaz/x-bookmarks/actions/workflows/sync.yml/dispatches \
  -d '{"ref":"main","inputs":{"triggered_by":"api"}}'
```
