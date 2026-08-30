"""
square_post.py

Publishes text posts to Binance Square using the official OpenAPI endpoint
(verified against Binance's own published "square-post" skill docs).

SECURITY: the API key is read ONLY from the environment (config.py).
It is never logged, never printed in full, never hard-coded.

NOTE ON IMAGES: This module currently posts TEXT ONLY. Binance Square's
image upload flow (presigned URL + polling before publish) was not fully
documented in what I could verify, so I'm not wiring up auto-image-attach
yet rather than guessing at an endpoint that might silently fail. The
graphic.py module still generates the image locally — ask if you want me
to research the upload flow further and wire it in as a second step.
"""

import requests
from src import config

SQUARE_POST_URL = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi/content/add"


def _mask(key: str) -> str:
    if not key or len(key) < 10:
        return "****"
    return f"{key[:5]}...{key[-4:]}"


def post_text(text: str) -> dict:
    api_key = config.BINANCE_SQUARE_OPENAPI_KEY
    if not api_key:
        raise RuntimeError("BINANCE_SQUARE_OPENAPI_KEY is not set in environment.")

    if not text or not text.strip():
        raise ValueError("Refusing to publish an empty post.")

    if len(text) > config.CHAR_LIMIT:
        raise ValueError(f"Post text is {len(text)} chars, over the {config.CHAR_LIMIT} limit.")

    headers = {
        "Content-Type": "application/json",
        "X-Square-OpenAPI-Key": api_key,
    }
    payload = {"content": text, "contentType": 1}

    resp = requests.post(SQUARE_POST_URL, json=payload, headers=headers, timeout=20)

    if resp.status_code == 504:
        print(
            f"[square_post] Got 504 using key {_mask(api_key)} — post likely went through "
            "server-side but no ID/link was returned. Verify manually on Binance Square."
        )
        return {"id": None, "link": None, "soft_success": True}

    try:
        data = resp.json()
    except Exception:
        data = None

    if not resp.ok or not data or data.get("code") != "000000":
        code = (data or {}).get("code", resp.status_code)
        message = (data or {}).get("message", "Unknown error")
        raise RuntimeError(f"Binance Square post failed [{code}]: {message}")

    post_id = (data.get("data") or {}).get("id")
    link = f"https://www.binance.com/en/square/post/{post_id}" if post_id else None

    return {"id": post_id, "link": link, "soft_success": False}
