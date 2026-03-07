# X Bookmarks Sync

Automatically syncs X (Twitter) bookmarks to Supabase and displays them on [aliberkyilmaz.com/bookmarks](https://aliberkyilmaz.com/bookmarks.html).

## How it works

1. **GitHub Actions** triggers `scripts/sync.py` (manually or via API)
2. The script logs in to X using `twikit`, fetches all bookmarks (paginated)
3. Each tweet is auto-tagged with 1-3 topic tags (AI, dev, design, etc.)
4. New bookmarks are upserted into Supabase (skips existing ones by `tweet_id`)
5. The bookmarks page fetches from Supabase and displays them in a filterable card grid

## Setup

### Required GitHub Secrets

| Secret | Value |
|--------|-------|
| `X_USERNAME` | Your X username |
| `X_PASSWORD` | Your X password |
| `SUPABASE_URL` | `https://xvedxjlsfxxgtegbjtws.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase service role key |

### Manual Trigger

Go to **Actions → Sync X Bookmarks → Run workflow** in GitHub, or trigger via API:

```bash
curl -X POST \
  -H "Authorization: token YOUR_GITHUB_PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  https://api.github.com/repos/AliberkYilmaz/x-bookmarks/actions/workflows/sync.yml/dispatches \
  -d '{"ref":"main","inputs":{"triggered_by":"api"}}'
```

## Bookmarks Page

Fill in these placeholders in `bookmarks.html` on aliberkyilmaz.com:

- `YOUR_GITHUB_PAT` — GitHub Personal Access Token with `repo` + `actions:write` scope
- `YOUR_SUPABASE_ANON_KEY` — Supabase project anon/public key
- `YOUR_GROQ_API_KEY` — Groq API key (free at console.groq.com)

## Auto-tagging

Tags are assigned by keyword matching:

| Tag | Example keywords |
|-----|-----------------|
| `AI` | gpt, llm, openai, claude, neural |
| `dev` | code, github, python, react, api |
| `design` | figma, ui, ux, typography |
| `marketing` | growth, seo, funnel, brand |
| `business` | startup, saas, revenue, founder |
| `productivity` | habits, notion, workflow, focus |
| `writing` | newsletter, essay, substack |
| `prompts` | prompt engineering, few-shot |
| `finance` | invest, crypto, stocks |
| `other` | anything else |
