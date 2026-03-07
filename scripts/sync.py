#!/usr/bin/env python3
"""
X Bookmarks Sync Script
Fetches all bookmarks from X (Twitter) via twikit and upserts them into Supabase.
"""

import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import create_client, Client
import twikit

load_dotenv()

# ── Credentials ──────────────────────────────────────────────────────────────
X_USERNAME = os.getenv("X_USERNAME")
X_PASSWORD = os.getenv("X_PASSWORD")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# ── Tag keywords ─────────────────────────────────────────────────────────────
TAG_KEYWORDS = {
    "AI": ["ai", "gpt", "llm", "machine learning", "deep learning", "neural", "openai",
           "anthropic", "claude", "gemini", "mistral", "stable diffusion", "midjourney",
           "artificial intelligence", "ml ", "chatgpt", "copilot", "rag", "embedding",
           "fine-tun", "foundation model", "transformer"],
    "dev": ["code", "coding", "developer", "programming", "software", "github", "git",
            "python", "javascript", "typescript", "react", "node", "api", "backend",
            "frontend", "fullstack", "devops", "kubernetes", "docker", "database",
            "sql", "nosql", "deploy", "framework", "library", "open source"],
    "design": ["design", "ui ", "ux ", "figma", "typography", "color", "layout",
               "visual", "graphic", "font", "spacing", "wireframe", "prototype",
               "interface", "aesthetic", "css", "animation", "motion"],
    "marketing": ["marketing", "growth", "seo", "email", "campaign", "funnel",
                  "conversion", "audience", "brand", "content marketing", "copywriting",
                  "ads", "social media", "engagement", "traffic", "lead", "viral"],
    "business": ["business", "startup", "entrepreneur", "revenue", "profit", "saas",
                 "b2b", "b2c", "product market fit", "mvp", "funding", "investor",
                 "vc ", "venture", "founder", "bootstrap", "scale", "market", "strategy",
                 "monetiz", "pricing", "customer"],
    "productivity": ["productivity", "habit", "routine", "focus", "system", "workflow",
                     "time management", "notion", "obsidian", "pkm", "second brain",
                     "zettelkasten", "gtd", "deep work", "async", "tool", "automation"],
    "writing": ["writing", "newsletter", "essay", "blog", "article", "story", "prose",
                "publish", "substack", "medium", "words", "sentence", "narrative",
                "content creation", "ghostwrit"],
    "prompts": ["prompt", "prompt engineering", "system prompt", "context window",
                "zero-shot", "few-shot", "chain of thought", "jailbreak", "temperature"],
    "finance": ["finance", "invest", "stock", "crypto", "bitcoin", "ethereum", "nft",
                "defi", "portfolio", "compound", "dividend", "etf", "wealth", "money",
                "saving", "budget", "return", "market cap"],
}


def auto_tag(text: str) -> list[str]:
    """Return 1-3 topic tags based on keyword matching."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for tag, keywords in TAG_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[tag] = count
    sorted_tags = sorted(scores, key=scores.get, reverse=True)
    result = sorted_tags[:3]
    if not result:
        result = ["other"]
    return result


def extract_tweet_data(tweet) -> dict:
    """Extract relevant fields from a twikit Tweet object."""
    try:
        author = tweet.user
        author_name = getattr(author, "name", "") or ""
        author_handle = getattr(author, "screen_name", "") or ""
        author_avatar = getattr(author, "profile_image_url_https", "") or ""

        tweet_id = str(tweet.id)
        text = getattr(tweet, "full_text", "") or getattr(tweet, "text", "") or ""
        tweet_url = f"https://x.com/{author_handle}/status/{tweet_id}"

        # posted_at
        posted_at = None
        raw_date = getattr(tweet, "created_at", None)
        if raw_date:
            try:
                posted_at = datetime.strptime(raw_date, "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                posted_at = str(raw_date)

        # Images
        images = []
        media = getattr(tweet, "media", None) or []
        for m in media:
            if getattr(m, "type", "") == "photo":
                url = getattr(m, "media_url_https", "") or getattr(m, "url", "")
                if url:
                    images.append(url)

        # Counts
        like_count = getattr(tweet, "favorite_count", 0) or 0
        retweet_count = getattr(tweet, "retweet_count", 0) or 0
        reply_count = getattr(tweet, "reply_count", 0) or 0

        # Quoted tweet
        quoted_tweet = None
        qt = getattr(tweet, "quoted_tweet", None)
        if qt:
            try:
                qt_author = qt.user
                qt_handle = getattr(qt_author, "screen_name", "") or ""
                qt_id = str(qt.id)
                qt_text = getattr(qt, "full_text", "") or getattr(qt, "text", "") or ""
                qt_images = []
                qt_media = getattr(qt, "media", None) or []
                for m in qt_media:
                    if getattr(m, "type", "") == "photo":
                        url = getattr(m, "media_url_https", "") or getattr(m, "url", "")
                        if url:
                            qt_images.append(url)
                quoted_tweet = {
                    "tweet_id": qt_id,
                    "text": qt_text,
                    "author_name": getattr(qt_author, "name", "") or "",
                    "author_handle": qt_handle,
                    "author_avatar_url": getattr(qt_author, "profile_image_url_https", "") or "",
                    "tweet_url": f"https://x.com/{qt_handle}/status/{qt_id}",
                    "posted_at": None,
                    "images": qt_images,
                    "like_count": getattr(qt, "favorite_count", 0) or 0,
                    "retweet_count": getattr(qt, "retweet_count", 0) or 0,
                    "reply_count": getattr(qt, "reply_count", 0) or 0,
                    "lang": getattr(qt, "lang", None),
                }
            except Exception as e:
                print(f"  ⚠️  Could not extract quoted tweet: {e}")

        lang = getattr(tweet, "lang", None)
        tags = auto_tag(text)

        return {
            "tweet_id": tweet_id,
            "text": text,
            "author_name": author_name,
            "author_handle": author_handle,
            "author_avatar_url": author_avatar,
            "tweet_url": tweet_url,
            "posted_at": posted_at,
            "images": images,
            "like_count": like_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "quoted_tweet": quoted_tweet,
            "tags": tags,
            "lang": lang,
        }
    except Exception as e:
        print(f"  ❌ Error extracting tweet {getattr(tweet, 'id', '?')}: {e}")
        return None


async def fetch_all_bookmarks(client: twikit.Client) -> list:
    """Fetch all bookmarks with pagination."""
    all_tweets = []
    cursor = None
    page = 1

    print("📥 Fetching bookmarks from X...")
    while True:
        try:
            if cursor:
                result = await client.get_bookmarks(cursor=cursor)
            else:
                result = await client.get_bookmarks()

            if not result:
                break

            tweets = list(result)
            if not tweets:
                break

            all_tweets.extend(tweets)
            print(f"  Page {page}: fetched {len(tweets)} bookmarks (total: {len(all_tweets)})")

            # Try to get next cursor
            next_cursor = getattr(result, "next_cursor", None)
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            page += 1

        except Exception as e:
            print(f"  ⚠️  Error fetching page {page}: {e}")
            break

    print(f"✅ Total bookmarks fetched: {len(all_tweets)}")
    return all_tweets


def upsert_to_supabase(supabase: Client, records: list[dict]) -> int:
    """Upsert records to Supabase, return count of newly inserted ones."""
    if not records:
        return 0

    # Get existing tweet_ids
    existing_ids = set()
    try:
        resp = supabase.table("bookmarks").select("tweet_id").execute()
        existing_ids = {row["tweet_id"] for row in (resp.data or [])}
        print(f"📊 Found {len(existing_ids)} existing bookmarks in Supabase")
    except Exception as e:
        print(f"  ⚠️  Could not fetch existing IDs: {e}")

    new_records = [r for r in records if r and r.get("tweet_id") not in existing_ids]
    print(f"🆕 {len(new_records)} new bookmarks to insert")

    if not new_records:
        return 0

    inserted = 0
    batch_size = 50
    for i in range(0, len(new_records), batch_size):
        batch = new_records[i:i + batch_size]
        try:
            supabase.table("bookmarks").upsert(batch, on_conflict="tweet_id").execute()
            inserted += len(batch)
            print(f"  ✅ Inserted batch {i // batch_size + 1}: {len(batch)} records")
        except Exception as e:
            print(f"  ❌ Error inserting batch {i // batch_size + 1}: {e}")

    return inserted


async def main():
    # Validate env
    missing = [v for v in ["X_USERNAME", "X_PASSWORD", "SUPABASE_URL", "SUPABASE_SERVICE_KEY"] if not os.getenv(v)]
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Init Supabase
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

    # Init twikit
    client = twikit.Client(language="en-US")
    cookies_file = "/tmp/x_cookies.json"

    print(f"🔐 Logging in to X as @{X_USERNAME}...")
    try:
        await client.login(
            auth_info_1=X_USERNAME,
            password=X_PASSWORD,
        )
        print("  ✅ Login successful")
    except Exception as e:
        print(f"  ❌ Login failed: {e}")
        sys.exit(1)

    # Fetch bookmarks
    tweets = await fetch_all_bookmarks(client)

    if not tweets:
        print("⚠️  No bookmarks found.")
        sys.exit(0)

    # Extract data
    print("🔄 Processing tweets...")
    records = []
    for t in tweets:
        data = extract_tweet_data(t)
        if data:
            records.append(data)

    print(f"📝 Processed {len(records)} valid records")

    # Upsert
    inserted = upsert_to_supabase(supabase, records)

    print(f"\n🎉 Done! Fetched {len(tweets)} bookmarks, inserted {inserted} new ones.")
    print(f"::set-output name=result::Fetched {len(tweets)} bookmarks, inserted {inserted} new ones.")


if __name__ == "__main__":
    asyncio.run(main())
