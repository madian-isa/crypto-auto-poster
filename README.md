# Crypto Auto-Poster (Binance Square)

Automatically finds relevant crypto/macro news, writes an honest fact-based
draft in the agreed house style, sends it to your Telegram for a quick
Approve/Reject tap, and only then publishes it to Binance Square.

## Flow

1. Finds relevant news (Finnhub free tier)
2. Writes a draft (rule-based, free — no Anthropic key needed)
3. Sends the draft to your Telegram with ✅ Approve / ❌ Reject buttons
4. Waits up to `APPROVAL_TIMEOUT_MINUTES` (default 60) for your tap
5. If approved → posts to Binance Square and confirms with a link in Telegram
6. If rejected or no response in time → skips it, moves to the next cycle

## What it does NOT do (by design)

- No fear/greed hooks ("is your money safe", "final crash", etc.)
- No invented price predictions or guaranteed targets
- No third-party news photos/videos attached (copyright risk) — generates
  its own simple data-card graphic instead (`src/graphic.py`, not yet
  auto-attached to posts — see limitation below)
- Stays conservative on posting frequency (default max 6/day, randomized
  timing) to avoid looking bot-like to Binance's recommendation algorithm

## Files

```
src/
  config.py             - reads all secrets from environment (never hard-coded)
  news_source.py        - fetches crypto/forex/macro news from Finnhub (free tier)
  content_generator.py  - writes headline/points/take (free rule-based version)
  post_template.py      - assembles final text: 2000 char limit, 3 $cashtags, 5 #hashtags
  graphic.py             - generates an original data-card image (no copyright risk)
  square_post.py        - publishes to Binance Square via the official OpenAPI endpoint
  telegram_approval.py  - sends draft + Approve/Reject buttons, waits for your tap
  dedupe.py             - tracks what's already been posted (seen_events.json)
  main.py               - the loop: poll -> draft -> Telegram approval -> post -> repeat
```

## Setup on Render (step by step)

1. Push this folder to a new GitHub repo (e.g. `crypto-auto-poster`).
2. On Render: **New +** -> **Background Worker** -> connect the GitHub repo.
3. Build command: `pip install -r requirements.txt`
4. Start command: `python -m src.main`
5. Go to the **Environment** tab and add these (as secrets, never in code):

   | Key | Value |
   |---|---|
   | `BINANCE_SQUARE_OPENAPI_KEY` | your Binance Square API key |
   | `FINNHUB_API_KEY` | free key from finnhub.io (no card needed) |
   | `TELEGRAM_BOT_TOKEN` | from @BotFather |
   | `TELEGRAM_CHAT_ID` | your chat ID (from the getUpdates trick) |
   | `ANTHROPIC_API_KEY` | optional — improves writing quality, costs a small amount per post |
   | `POLL_INTERVAL_MINUTES` | optional, default `10` |
   | `MAX_POSTS_PER_DAY` | optional, default `6` |
   | `APPROVAL_TIMEOUT_MINUTES` | optional, default `60` |

6. Deploy. Check the **Logs** tab to confirm it's running.
7. **Important:** both the API keys shown in your screenshots earlier
   (Binance and Telegram) should be regenerated before going live, since
   they were visible in this chat.

## Important limitations to know about

- **Ephemeral disk:** Render's free tier resets `seen_events.json` on every
  redeploy/restart, which could rarely cause a re-send of an old draft.
  Not a big deal, but worth knowing.
- **Image auto-attach:** `graphic.py` generates the image, but it is not
  yet wired into the Telegram draft or the Binance post — the upload flow
  needs more verification first. Ask if you want this finished next.
- **Approval must happen from the same Render instance run** — if the
  worker restarts while a draft is pending, that pending draft is lost
  (it'll just get skipped, not double-posted).

## Testing before going live

Run one cycle locally first to see what it *would* send to Telegram,
without needing the Binance key yet:

```bash
pip install -r requirements.txt
export FINNHUB_API_KEY=your_key_here
export TELEGRAM_BOT_TOKEN=your_token_here
export TELEGRAM_CHAT_ID=your_chat_id_here
python3 -c "from src import main; main.run_once()"
```
