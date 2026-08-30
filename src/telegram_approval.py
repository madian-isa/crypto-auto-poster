"""
telegram_approval.py

Sends a draft post to your Telegram chat with inline "Approve" / "Reject"
buttons. Nothing gets published to Binance until you tap Approve.

SECURITY: token and chat ID are read from environment variables only:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import requests
from src import config

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


def _api(method, **params):
    url = TELEGRAM_API.format(token=config.TELEGRAM_BOT_TOKEN, method=method)
    resp = requests.post(url, json=params, timeout=15)
    resp.raise_for_status()
    return resp.json()


def send_draft_for_approval(draft_id: str, post_text: str) -> dict:
    """
    Sends the draft text with inline Approve/Reject buttons.
    draft_id is a short string used to match the button press back to the
    right draft later (main.py keeps the pending draft in memory/file).
    """
    message = f"📝 New draft ready for review:\n\n{post_text}\n\n— Reply with the buttons below —"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Approve & Post", "callback_data": f"approve:{draft_id}"},
                {"text": "❌ Reject", "callback_data": f"reject:{draft_id}"},
            ]
        ]
    }

    return _api(
        "sendMessage",
        chat_id=config.TELEGRAM_CHAT_ID,
        text=message,
        reply_markup=keyboard,
    )


def get_updates(offset=None):
    """Poll for new button presses (callback_query updates)."""
    params = {"timeout": 20}
    if offset is not None:
        params["offset"] = offset
    return _api("getUpdates", **params)


def answer_callback(callback_query_id, text=""):
    """Acknowledge the button press so Telegram stops showing the loading spinner."""
    return _api("answerCallbackQuery", callback_query_id=callback_query_id, text=text)


def notify(text: str):
    """Send a plain notification (e.g. 'Posted successfully: <link>')."""
    return _api("sendMessage", chat_id=config.TELEGRAM_CHAT_ID, text=text)
