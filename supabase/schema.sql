-- Replaces the previous twikit-shaped bookmarks table.
-- Run this before the first twitter-cli sync. The next sync repopulates the table.

begin;

drop table if exists public.bookmarks;

create table public.bookmarks (
  id text primary key,
  text text not null,
  author jsonb not null,
  metrics jsonb not null,
  created_at text not null,
  created_at_ts timestamptz,
  media jsonb not null default '[]'::jsonb,
  urls jsonb not null default '[]'::jsonb,
  is_retweet boolean not null default false,
  retweeted_by text,
  lang text,
  score double precision,
  article_title text,
  article_text text,
  quoted_tweet jsonb,
  tags text[] not null default '{}'::text[],
  tweet_url text,
  synced_at timestamptz not null default timezone('utc', now()),
  constraint bookmarks_author_is_object check (jsonb_typeof(author) = 'object'),
  constraint bookmarks_metrics_is_object check (jsonb_typeof(metrics) = 'object'),
  constraint bookmarks_media_is_array check (jsonb_typeof(media) = 'array'),
  constraint bookmarks_urls_is_array check (jsonb_typeof(urls) = 'array'),
  constraint bookmarks_quoted_tweet_is_object check (
    quoted_tweet is null or jsonb_typeof(quoted_tweet) = 'object'
  )
);

alter table public.bookmarks enable row level security;

grant select on public.bookmarks to anon, authenticated;
grant all privileges on public.bookmarks to service_role;

create policy "Public can read bookmarks"
on public.bookmarks
for select
to anon, authenticated
using (true);

create index bookmarks_created_at_ts_idx on public.bookmarks (created_at_ts desc nulls last);
create index bookmarks_synced_at_idx on public.bookmarks (synced_at desc);
create index bookmarks_tags_idx on public.bookmarks using gin (tags);

commit;
