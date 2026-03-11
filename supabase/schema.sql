-- Supabase bookmarks table for x-bookmarks sync.
-- Matches the actual deployed table schema (snake_case columns).

begin;

drop table if exists public.bookmarks;

create table public.bookmarks (
  id             uuid primary key default gen_random_uuid(),
  tweet_id       text unique not null,
  text           text,
  author_name    text,
  author_handle  text,
  author_avatar_url text,
  like_count     integer not null default 0,
  reply_count    integer not null default 0,
  retweet_count  integer not null default 0,
  posted_at      timestamptz,
  lang           text,
  images         text[] not null default '{}',
  quoted_tweet   jsonb,
  tags           text[] not null default '{}',
  tweet_url      text,
  synced_at      timestamptz not null default now()
);

create index bookmarks_synced_at_idx on public.bookmarks (synced_at desc);
create index bookmarks_tags_idx on public.bookmarks using gin (tags);
create unique index bookmarks_tweet_id_idx on public.bookmarks (tweet_id);

alter table public.bookmarks enable row level security;

grant select on public.bookmarks to anon, authenticated;
grant all privileges on public.bookmarks to service_role;

drop policy if exists "Public can read bookmarks" on public.bookmarks;
create policy "Public can read bookmarks"
on public.bookmarks
for select
to anon, authenticated
using (true);

commit;
