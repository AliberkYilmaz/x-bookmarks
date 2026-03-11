#!/usr/bin/env python3
"""
Sync X bookmarks from twitter-cli into Supabase.
Maps camelCase twitter-cli JSON → snake_case Supabase columns.
"""

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

REQUIRED_ENV_VARS = (
    "TWITTER_AUTH_TOKEN",
    "TWITTER_CT0",
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
)

TAG_KEYWORDS = {
    "AI": ["ai", "gpt", "llm", "machine learning", "deep learning", "neural", "openai", "anthropic", "claude", "gemini", "mistral", "stable diffusion", "midjourney", "artificial intelligence", "ml ", "chatgpt", "copilot", "rag", "embedding", "fine-tun", "foundation model", "transformer"],
    "dev": ["code", "coding", "developer", "programming", "software", "github", "git", "python", "javascript", "typescript", "react", "node", "api", "backend", "frontend", "fullstack", "devops", "kubernetes", "docker", "database", "sql", "nosql", "deploy", "framework", "library", "open source"],
    "design": ["design", "ui ", "ux ", "figma", "typography", "color", "layout", "visual", "graphic", "font", "spacing", "wireframe", "prototype", "interface", "aesthetic", "css", "animation", "motion"],
    "marketing": ["marketing", "growth", "seo", "email", "campaign", "funnel", "conversion", "audience", "brand", "content marketing", "copywriting", "ads", "social media", "engagement", "traffic", "lead", "viral"],
    "business": ["business", "startup", "entrepreneur", "revenue", "profit", "saas", "b2b", "b2c", "product market fit", "mvp", "funding", "investor", "vc ", "venture", "founder", "bootstrap", "scale", "market", "strategy", "monetiz", "pricing", "customer"],
    "productivity": ["productivity", "habit", "routine", "focus", "system", "workflow", "time management", "notion", "obsidian", "pkm", "second brain", "zettelkasten", "gtd", "deep work", "async", "tool", "automation"],
    "writing": ["writing", "newsletter", "essay", "blog", "article", "story", "prose", "publish", "substack", "medium", "words", "sentence", "narrative", "content creation", "ghostwrit"],
    "prompts": ["prompt", "prompt engineering", "system prompt", "context window", "zero-shot", "few-shot", "chain of thought", "jailbreak", "temperature"],
    "finance": ["finance", "invest", "stock", "crypto", "bitcoin", "ethereum", "nft", "defi", "portfolio", "compound", "dividend", "etf", "wealth", "money", "saving", "budget", "return", "market cap"],
}


def fail(message: str, exit_code: int = 1) -> None:
    print(f"❌ {message}")
    sys.exit(exit_code)


def auto_tag(text: str) -> list[str]:
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for tag, keywords in TAG_KEYWORDS.items():
        count = sum(1 for kw in keywords if kw in text_lower)
        if count > 0:
            scores[tag] = count
    sorted_tags = sorted(scores, key=scores.get, reverse=True)
    return sorted_tags[:3] or ["other"]


def require_env_vars() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")


def build_tweet_url(tweet_id: str, author: dict) -> str | None:
    screen_name = author.get("screenName")
    if isinstance(screen_name, str) and screen_name:
        return f"https://x.com/{screen_name}/status/{tweet_id}"
    return None


def extract_image_urls(media: list) -> list[str]:
    """Extract image URLs from twitter-cli media array."""
    if not isinstance(media, list):
        return []
    urls = []
    for item in media:
        if isinstance(item, dict):
            url = item.get("url") or item.get("media_url_https") or item.get("mediaUrl")
            if url:
                urls.append(str(url))
    return urls


def map_tweet_to_record(tweet: dict, synced_at: str) -> dict:
    """Map a twitter-cli tweet object to Supabase bookmarks row (snake_case)."""
    tweet_id = str(tweet.get("id") or "").strip()
    if not tweet_id:
        raise ValueError("Missing id")

    author = tweet.get("author") or {}
    metrics = tweet.get("metrics") or {}

    # Build tag source from text + article fields
    tag_source = " ".join(filter(None, [
        str(tweet.get("text") or ""),
        str(tweet.get("articleTitle") or ""),
        str(tweet.get("articleText") or ""),
    ]))

    tweet_url = build_tweet_url(tweet_id, author)
    images = extract_image_urls(tweet.get("media") or [])

    # Map to the actual Supabase table columns (snake_case)
    return {
        "tweet_id": tweet_id,
        "text": str(tweet.get("text") or ""),
        "author_name": str(author.get("name") or ""),
        "author_handle": str(author.get("screenName") or author.get("screen_name") or ""),
        "author_avatar_url": str(author.get("avatarUrl") or author.get("avatar_url") or ""),
        "like_count": int(metrics.get("likeCount") or metrics.get("like_count") or 0),
        "reply_count": int(metrics.get("replyCount") or metrics.get("reply_count") or 0),
        "retweet_count": int(metrics.get("retweetCount") or metrics.get("retweet_count") or 0),
        "posted_at": tweet.get("createdAt") or tweet.get("created_at") or None,
        "lang": tweet.get("lang") or None,
        "images": images if images else [],
        "quoted_tweet": tweet.get("quotedTweet") or tweet.get("quoted_tweet") or None,
        "tags": auto_tag(tag_source),
        "tweet_url": tweet_url,
        "synced_at": synced_at,
    }


def fetch_bookmarks_from_twitter_cli() -> list[dict]:
    twitter_binary = os.getenv("TWITTER_CLI_BIN", "twitter")
    if shutil.which(twitter_binary) is None:
        fail(f"twitter-cli binary '{twitter_binary}' was not found on PATH. Make sure requirements are installed.")

    command = [twitter_binary, "bookmarks", "--json"]
    print(f"📥 Fetching bookmarks with {' '.join(command)}")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            env=os.environ.copy(),
        )
    except OSError as exc:
        fail(f"Failed to start twitter-cli: {exc}")

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    if result.returncode != 0:
        details = stderr or stdout or "twitter-cli exited without any output"
        fail(f"twitter-cli exited with code {result.returncode}: {details[:1000]}")

    if not stdout:
        fail("twitter-cli returned empty stdout; expected a JSON envelope")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        fail(f"twitter-cli returned malformed JSON: {exc}")

    if not isinstance(payload, dict):
        fail("twitter-cli returned a non-object payload; expected a JSON envelope")

    if payload.get("ok") is not True:
        fail(f"twitter-cli reported an unsuccessful response: {json.dumps(payload)}")

    data = payload.get("data")
    if not isinstance(data, list):
        fail("twitter-cli JSON envelope is missing the bookmarks data array")

    print(f"✅ twitter-cli returned {len(data)} bookmarks")
    return data


def fetch_existing_tweet_ids(supabase: Client) -> set[str]:
    try:
        response = supabase.table("bookmarks").select("tweet_id").execute()
    except Exception as exc:
        fail(f"Could not query public.bookmarks in Supabase.\nDetails: {exc}")
    return {str(row["tweet_id"]) for row in (response.data or []) if row.get("tweet_id")}


def upsert_to_supabase(supabase: Client, records: list[dict]) -> tuple[int, int]:
    if not records:
        return (0, 0)

    existing_ids = fetch_existing_tweet_ids(supabase)
    new_count = sum(1 for r in records if r["tweet_id"] not in existing_ids)

    written = 0
    batch_size = 50
    for index in range(0, len(records), batch_size):
        batch = records[index : index + batch_size]
        batch_number = (index // batch_size) + 1
        try:
            supabase.table("bookmarks").upsert(batch, on_conflict="tweet_id").execute()
            written += len(batch)
            print(f"  ✅ Upserted batch {batch_number}: {len(batch)} records")
        except Exception as exc:
            fail(f"Supabase upsert failed for batch {batch_number}.\nDetails: {exc}")

    return (new_count, written)


def main() -> None:
    require_env_vars()

    print("🔐 Using twitter-cli cookie secrets from environment")
    bookmarks = fetch_bookmarks_from_twitter_cli()

    if not bookmarks:
        print("⚠️  twitter-cli returned zero bookmarks; nothing to sync.")
        return

    print("🔄 Mapping bookmarks to Supabase schema...")
    synced_at = datetime.now(timezone.utc).isoformat()
    records = []
    skipped = 0

    for tweet in bookmarks:
        try:
            record = map_tweet_to_record(tweet, synced_at)
            records.append(record)
        except Exception as exc:
            skipped += 1
            print(f"  ⚠️  Skipping malformed bookmark: {exc}")

    if not records:
        fail("All bookmarks were malformed; nothing was written")

    print(f"📝 Prepared {len(records)} records for upsert ({skipped} skipped)")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    new_count, written = upsert_to_supabase(supabase, records)

    print(f"\n🎉 Done! Processed {len(bookmarks)} bookmarks, upserted {written} rows, {new_count} of them new.")


if __name__ == "__main__":
    main()
