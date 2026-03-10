#!/usr/bin/env python3
"""
Sync X bookmarks from twitter-cli into Supabase.
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
    "AI": [
        "ai",
        "gpt",
        "llm",
        "machine learning",
        "deep learning",
        "neural",
        "openai",
        "anthropic",
        "claude",
        "gemini",
        "mistral",
        "stable diffusion",
        "midjourney",
        "artificial intelligence",
        "ml ",
        "chatgpt",
        "copilot",
        "rag",
        "embedding",
        "fine-tun",
        "foundation model",
        "transformer",
    ],
    "dev": [
        "code",
        "coding",
        "developer",
        "programming",
        "software",
        "github",
        "git",
        "python",
        "javascript",
        "typescript",
        "react",
        "node",
        "api",
        "backend",
        "frontend",
        "fullstack",
        "devops",
        "kubernetes",
        "docker",
        "database",
        "sql",
        "nosql",
        "deploy",
        "framework",
        "library",
        "open source",
    ],
    "design": [
        "design",
        "ui ",
        "ux ",
        "figma",
        "typography",
        "color",
        "layout",
        "visual",
        "graphic",
        "font",
        "spacing",
        "wireframe",
        "prototype",
        "interface",
        "aesthetic",
        "css",
        "animation",
        "motion",
    ],
    "marketing": [
        "marketing",
        "growth",
        "seo",
        "email",
        "campaign",
        "funnel",
        "conversion",
        "audience",
        "brand",
        "content marketing",
        "copywriting",
        "ads",
        "social media",
        "engagement",
        "traffic",
        "lead",
        "viral",
    ],
    "business": [
        "business",
        "startup",
        "entrepreneur",
        "revenue",
        "profit",
        "saas",
        "b2b",
        "b2c",
        "product market fit",
        "mvp",
        "funding",
        "investor",
        "vc ",
        "venture",
        "founder",
        "bootstrap",
        "scale",
        "market",
        "strategy",
        "monetiz",
        "pricing",
        "customer",
    ],
    "productivity": [
        "productivity",
        "habit",
        "routine",
        "focus",
        "system",
        "workflow",
        "time management",
        "notion",
        "obsidian",
        "pkm",
        "second brain",
        "zettelkasten",
        "gtd",
        "deep work",
        "async",
        "tool",
        "automation",
    ],
    "writing": [
        "writing",
        "newsletter",
        "essay",
        "blog",
        "article",
        "story",
        "prose",
        "publish",
        "substack",
        "medium",
        "words",
        "sentence",
        "narrative",
        "content creation",
        "ghostwrit",
    ],
    "prompts": [
        "prompt",
        "prompt engineering",
        "system prompt",
        "context window",
        "zero-shot",
        "few-shot",
        "chain of thought",
        "jailbreak",
        "temperature",
    ],
    "finance": [
        "finance",
        "invest",
        "stock",
        "crypto",
        "bitcoin",
        "ethereum",
        "nft",
        "defi",
        "portfolio",
        "compound",
        "dividend",
        "etf",
        "wealth",
        "money",
        "saving",
        "budget",
        "return",
        "market cap",
    ],
}


def fail(message: str, exit_code: int = 1) -> None:
    """Print a clear error and exit."""
    print(f"❌ {message}")
    sys.exit(exit_code)


def auto_tag(text: str) -> list[str]:
    """Return 1-3 topic tags based on keyword matching."""
    text_lower = text.lower()
    scores: dict[str, int] = {}
    for tag, keywords in TAG_KEYWORDS.items():
        count = sum(1 for keyword in keywords if keyword in text_lower)
        if count > 0:
            scores[tag] = count

    sorted_tags = sorted(scores, key=scores.get, reverse=True)
    return sorted_tags[:3] or ["other"]


def require_env_vars() -> None:
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        fail(f"Missing environment variables: {', '.join(missing)}")


def parse_timestamp(value: str | None) -> str | None:
    """Normalize timestamp strings when possible."""
    if not value:
        return None

    iso_candidate = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).astimezone(timezone.utc).isoformat()
    except ValueError:
        pass

    for pattern in (
        "%a %b %d %H:%M:%S %z %Y",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            parsed = datetime.strptime(value, pattern)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()
        except ValueError:
            continue

    return None


def build_tweet_url(tweet_id: str, author: dict) -> str | None:
    screen_name = author.get("screenName")
    if isinstance(screen_name, str) and screen_name:
        return f"https://x.com/{screen_name}/status/{tweet_id}"
    return None


def normalize_author(value: object, tweet_id: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Tweet {tweet_id} is missing an author object")

    return {
        "id": str(value.get("id") or ""),
        "name": str(value.get("name") or ""),
        "screenName": str(value.get("screenName") or ""),
        "profileImageUrl": str(value.get("profileImageUrl") or ""),
        "verified": bool(value.get("verified", False)),
    }


def normalize_metrics(value: object, tweet_id: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"Tweet {tweet_id} is missing a metrics object")

    keys = ("likes", "retweets", "replies", "quotes", "views", "bookmarks")
    metrics: dict[str, int] = {}
    for key in keys:
        raw = value.get(key, 0)
        try:
            metrics[key] = int(raw or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Tweet {tweet_id} has invalid metrics.{key}: {raw!r}") from exc
    return metrics


def normalize_media(value: object) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("media must be a list")

    media_items = []
    for item in value:
        if not isinstance(item, dict):
            continue
        media_items.append(
            {
                "type": str(item.get("type") or ""),
                "url": str(item.get("url") or ""),
                "width": item.get("width"),
                "height": item.get("height"),
            }
        )
    return media_items


def normalize_urls(value: object) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("urls must be a list")
    return [str(item) for item in value if item]


def normalize_quoted_tweet(value: object) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("quotedTweet must be an object or null")

    author = value.get("author")
    if author is not None and not isinstance(author, dict):
        raise ValueError("quotedTweet.author must be an object")

    normalized_author = {
        "screenName": str((author or {}).get("screenName") or ""),
        "name": str((author or {}).get("name") or ""),
    }

    return {
        "id": str(value.get("id") or ""),
        "text": str(value.get("text") or ""),
        "author": normalized_author,
    }


def normalize_tweet(tweet: object, synced_at: str) -> dict:
    if not isinstance(tweet, dict):
        raise ValueError("Bookmark payload item is not an object")

    tweet_id = str(tweet.get("id") or "").strip()
    if not tweet_id:
        raise ValueError("Bookmark payload item is missing id")

    author = normalize_author(tweet.get("author"), tweet_id)
    created_at = tweet.get("createdAt")
    if not isinstance(created_at, str) or not created_at.strip():
        raise ValueError(f"Tweet {tweet_id} is missing createdAt")

    article_title = tweet.get("articleTitle")
    article_text = tweet.get("articleText")
    tag_source = " ".join(
        value
        for value in (
            str(tweet.get("text") or ""),
            str(article_title or ""),
            str(article_text or ""),
        )
        if value
    )

    score = tweet.get("score")
    if score is not None:
        try:
            score = float(score)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Tweet {tweet_id} has invalid score: {score!r}") from exc

    media = normalize_media(tweet.get("media"))
    urls = normalize_urls(tweet.get("urls"))
    quoted_tweet = normalize_quoted_tweet(tweet.get("quotedTweet"))

    return {
        "id": tweet_id,
        "text": str(tweet.get("text") or ""),
        "author": author,
        "metrics": normalize_metrics(tweet.get("metrics"), tweet_id),
        "created_at": created_at,
        "created_at_ts": parse_timestamp(created_at),
        "media": media,
        "urls": urls,
        "is_retweet": bool(tweet.get("isRetweet", False)),
        "retweeted_by": str(tweet.get("retweetedBy") or "") or None,
        "lang": str(tweet.get("lang") or "") or None,
        "score": score,
        "article_title": str(article_title or "") or None,
        "article_text": str(article_text or "") or None,
        "quoted_tweet": quoted_tweet,
        "tags": auto_tag(tag_source or str(tweet.get("text") or "")),
        "tweet_url": build_tweet_url(tweet_id, author),
        "synced_at": synced_at,
    }


def fetch_bookmarks_from_twitter_cli() -> list[dict]:
    """Fetch bookmarks by shelling out to twitter-cli."""
    twitter_binary = os.getenv("TWITTER_CLI_BIN", "twitter")
    if shutil.which(twitter_binary) is None:
        fail(
            f"twitter-cli binary '{twitter_binary}' was not found on PATH. "
            "Make sure requirements are installed in the GitHub Actions job."
        )

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

    success = payload.get("success")
    if not isinstance(success, dict):
        fail("twitter-cli JSON envelope is missing success metadata")

    if success.get("ok") is not True:
        fail(f"twitter-cli reported an unsuccessful response: {json.dumps(success)}")

    schema_version = success.get("schema_version")
    if not isinstance(schema_version, str):
        fail("twitter-cli JSON envelope is missing schema_version")
    if schema_version != "1":
        print(f"⚠️  Unexpected twitter-cli schema_version '{schema_version}', continuing cautiously")

    data = success.get("data")
    if not isinstance(data, list):
        fail("twitter-cli JSON envelope is missing the bookmarks data array")

    print(f"✅ twitter-cli returned {len(data)} bookmarks")
    return data


def fetch_existing_ids(supabase: Client) -> set[str]:
    try:
        response = supabase.table("bookmarks").select("id").execute()
    except Exception as exc:
        fail(
            "Could not query public.bookmarks in Supabase. "
            "Apply supabase/schema.sql before running the workflow.\n"
            f"Details: {exc}"
        )

    return {str(row["id"]) for row in (response.data or []) if row.get("id")}


def upsert_to_supabase(supabase: Client, records: list[dict]) -> tuple[int, int]:
    """Upsert records and return (new_count, total_written)."""
    if not records:
        return (0, 0)

    existing_ids = fetch_existing_ids(supabase)
    new_count = sum(1 for record in records if record["id"] not in existing_ids)

    written = 0
    batch_size = 50
    for index in range(0, len(records), batch_size):
        batch = records[index : index + batch_size]
        batch_number = (index // batch_size) + 1
        try:
            supabase.table("bookmarks").upsert(batch, on_conflict="id").execute()
            written += len(batch)
            print(f"  ✅ Upserted batch {batch_number}: {len(batch)} records")
        except Exception as exc:
            fail(
                f"Supabase upsert failed for batch {batch_number}. "
                "Check that public.bookmarks matches supabase/schema.sql.\n"
                f"Details: {exc}"
            )

    return (new_count, written)


def main() -> None:
    require_env_vars()

    print("🔐 Using twitter-cli cookie secrets from GitHub Actions")
    bookmarks = fetch_bookmarks_from_twitter_cli()

    if not bookmarks:
        print("⚠️  twitter-cli returned zero bookmarks; nothing to sync.")
        return

    print("🔄 Normalizing bookmarks for Supabase...")
    synced_at = datetime.now(timezone.utc).isoformat()
    records = []
    skipped = 0

    for bookmark in bookmarks:
        try:
            records.append(normalize_tweet(bookmark, synced_at))
        except ValueError as exc:
            skipped += 1
            print(f"  ⚠️  Skipping malformed bookmark: {exc}")

    if not records:
        fail("All bookmarks were malformed after normalization; nothing was written")

    print(f"📝 Prepared {len(records)} records for upsert ({skipped} skipped)")

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    new_count, written = upsert_to_supabase(supabase, records)

    print(
        f"\n🎉 Done! Processed {len(bookmarks)} bookmarks, "
        f"upserted {written} rows, {new_count} of them new."
    )


if __name__ == "__main__":
    main()
