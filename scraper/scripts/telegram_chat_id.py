"""
Find your Telegram chat_id — one-time setup helper.

Usage:
  1. Open Telegram and send any message (e.g. "hi") to your bot.
  2. uv run python scripts/telegram_chat_id.py
  3. Paste the printed id into scraper/.env as TELEGRAM_CHAT_ID=...

Telegram only returns updates for chats that have messaged the bot, and it
drops them after 24h — so step 1 has to happen shortly before step 2.
"""

import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402


def main() -> None:
    if not settings.telegram_token:
        print("TELEGRAM_TOKEN is not set in scraper/.env")
        raise SystemExit(1)

    url = f"https://api.telegram.org/bot{settings.telegram_token}/getUpdates"

    try:
        response = httpx.get(url, timeout=15)
    except Exception as exc:
        print(f"Request failed: {exc}")
        raise SystemExit(1) from exc

    if response.status_code != 200:
        print(f"Telegram returned {response.status_code}: {response.text}")
        raise SystemExit(1)

    updates = response.json().get("result", [])

    chats: dict[str, str] = {}
    for update in updates:
        message = update.get("message") or update.get("channel_post") or {}
        chat = message.get("chat")
        if not chat:
            continue
        label = chat.get("title") or chat.get("username") or chat.get("first_name") or "?"
        chats[str(chat["id"])] = f"{label} ({chat.get('type', '?')})"

    if not chats:
        print("No chats found.")
        print()
        print("Send any message to your bot in Telegram, then re-run this script.")
        print("(Telegram discards updates older than 24h.)")
        raise SystemExit(1)

    print("Found chat(s):")
    print()
    for chat_id, label in chats.items():
        print(f"  {chat_id}  —  {label}")
    print()
    print("Add the one you want to scraper/.env:")
    print(f"  TELEGRAM_CHAT_ID={next(iter(chats))}")


if __name__ == "__main__":
    main()
