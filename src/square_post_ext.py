"""
square_post_ext.py

Extends your existing square_post.py with IMAGE posting support, ported
directly from Binance's own official "square-post" skill (lib.mjs) —
same endpoints, same presigned-upload + poll + publish flow, just in Python.

Drop this file next to square_post.py in your src/ package. It reuses
config.BINANCE_SQUARE_OPENAPI_KEY, so no new secrets to set up.

Flow (matches lib.mjs exactly):
  1. POST /image/presignedUrl  -> { presignedUrl, fileTicket }
  2. PUT the raw image bytes to presignedUrl (S3, not Binance)
  3. Poll POST /image/imageStatus with fileTicket until status == 1 (ready)
  4. POST /content/add with contentType=1 and imageList=[imageUrl, ...]
"""

import time
import requests
from src import config

BASE_URL_V1 = "https://www.binance.com/bapi/composite/v1/public/pgc/openApi"
BASE_URL_V2 = "https://www.binance.com/bapi/composite/v2/public/pgc/openApi"
POLL_INTERVAL_SECONDS = 3
MAX_POLL_RETRIES = 10

_CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg", "jpeg": "image/jpeg",
    "png": "image/png", "gif": "image/gif", "webp": "image/webp",
}


def _mask(key: str) -> str:
    if not key or len(key) < 10:
        return "****"
    return f"{key[:5]}...{key[-4:]}"


def _get_content_type(file_path: str) -> str:
    ext = file_path.rsplit(".", 1)[-1].lower()
    return _CONTENT_TYPE_MAP.get(ext, "application/octet-stream")


def _api(endpoint: str, api_key: str, body: dict, base_url: str = BASE_URL_V2) -> dict:
    headers = {
        "X-Square-OpenAPI-Key": api_key,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill",
    }
    resp = requests.post(f"{base_url}{endpoint}", json=body, headers=headers, timeout=20)

    if endpoint == "/content/add" and resp.status_code == 504:
        return {"id": None, "shareLink": None, "publishStatus": "success_without_post_id"}

    try:
        data = resp.json()
    except ValueError as err:
        raise RuntimeError(
            f"API returned non-JSON response: {resp.status_code} {resp.reason}"
        ) from err

    if data.get("code") != "000000":
        raise RuntimeError(f"API error [{data.get('code')}]: {data.get('message')}")

    return data.get("data", {})


def _upload_to_s3(presigned_url: str, file_path: str, content_type: str) -> None:
    with open(file_path, "rb") as f:
        file_bytes = f.read()
    resp = requests.put(presigned_url, data=file_bytes, headers={"Content-Type": content_type}, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"S3 upload failed: {resp.status_code} {resp.reason}")


def _poll_image_status(api_key: str, file_ticket: str) -> dict:
    for attempt in range(MAX_POLL_RETRIES):
        data = _api("/image/imageStatus", api_key, {"fileTicket": file_ticket})
        if data.get("status") == 1:
            return data
        if data.get("status") == 2:
            raise RuntimeError(f"Image processing failed: {data.get('failedReason')}")
        print(f"[square_post_ext] processing... ({attempt + 1}/{MAX_POLL_RETRIES})")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise RuntimeError(f"Poll timed out after {MAX_POLL_RETRIES} retries")


def upload_image(api_key: str, image_path: str) -> str:
    """Uploads one local image file and returns the ready-to-use imageUrl."""
    content_type = _get_content_type(image_path)
    image_name = image_path.rsplit("/", 1)[-1]

    print(f"[square_post_ext] uploading: {image_name}")
    presigned = _api("/image/presignedUrl", api_key, {"imageName": image_name})

    _upload_to_s3(presigned["presignedUrl"], image_path, content_type)
    print("[square_post_ext] uploaded to S3, polling status...")

    status = _poll_image_status(api_key, presigned["fileTicket"])
    print(f"[square_post_ext] ready: {status['imageUrl']}")
    return status["imageUrl"]


def post_with_images(text: str, image_paths: list[str]) -> dict:
    """
    Publishes a text post with up to 4 images attached.
    Mirrors square_post.post_text()'s validation + error handling.
    """
    api_key = config.BINANCE_SQUARE_OPENAPI_KEY
    if not api_key:
        raise RuntimeError("BINANCE_SQUARE_OPENAPI_KEY is not set in environment.")

    if not text or not text.strip():
        raise ValueError("Refusing to publish an empty post.")

    if len(text) > config.CHAR_LIMIT:
        raise ValueError(f"Post text is {len(text)} chars, over the {config.CHAR_LIMIT} limit.")

    if not image_paths or len(image_paths) > 4:
        raise ValueError("post_with_images requires 1 to 4 image paths.")

    image_urls = [upload_image(api_key, p) for p in image_paths]

    payload = {"content": text, "contentType": 1, "imageList": image_urls}
    data = _api("/content/add", api_key, payload, BASE_URL_V1)

    post_id = data.get("id")
    link = f"https://www.binance.com/en/square/post/{post_id}" if post_id else None

    return {"id": post_id, "link": link, "soft_success": data.get("publishStatus") == "success_without_post_id"}
