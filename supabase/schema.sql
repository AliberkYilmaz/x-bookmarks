-- Replaces the previous twikit-shaped bookmarks table.
-- Run this before the first twitter-cli sync.

begin;

drop table if exists public.bookmarks;

create table public.bookmarks (
  "id" text primary key,
  "text" text not null,
  "author" jsonb not null,
  "metrics" jsonb not null,
  "createdAt" text not null,
  "media" jsonb not null default '[]'::jsonb,
  "urls" jsonb not null default '[]'::jsonb,
  "isRetweet" boolean not null default false,
  "retweetedBy" text,
  "lang" text,
  "score" double precision,
  "articleTitle" text,
  "articleText" text,
  "quotedTweet" jsonb,
  
  -- Derived metadata
  "tags" text[] not null default '{}'::text[],
  "tweetUrl" text,
  "syncedAt" timestamptz not null default timezone('utc', now())
);

create index "bookmarks_syncedAt_idx" on public.bookmarks ("syncedAt" desc);
create index "bookmarks_tags_idx" on public.bookmarks using gin ("tags");

commit;