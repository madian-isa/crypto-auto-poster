"""
square_post_ext.py

Binance Square text + image posting support.

Flow:
1. Request presigned image URL
2. Upload image to S3
3. Poll image processing status
4. Publish Square post with text + image
"""

import time
import requests

from src import config


BASE_URL_V1 = (
    "https://www.binance.com/"
    "bapi/composite/v1/public/pgc/openApi"
)

BASE_URL_V2 = (
    "https://www.binance.com/"
    "bapi/composite/v2/public/pgc/openApi"
)

POLL_INTERVAL_SECONDS = 3
MAX_POLL_RETRIES = 10


_CONTENT_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
}


def _mask(key: str) -> str:
    """Mask API key for safe logging."""

    if not key or len(key) < 10:
        return "****"

    return f"{key[:5]}...{key[-4:]}"


def _get_content_type(file_path: str) -> str:
    """Return MIME type from image extension."""

    ext = file_path.rsplit(".", 1)[-1].lower()

    return _CONTENT_TYPE_MAP.get(
        ext,
        "application/octet-stream",
    )


def _api(
    endpoint: str,
    api_key: str,
    body: dict,
    base_url: str = BASE_URL_V2,
) -> dict:
    """
    Call Binance Square OpenAPI.
    """

    headers = {
        "X-Square-OpenAPI-Key": api_key,
        "Content-Type": "application/json",
        "clienttype": "binanceSkill",
    }

    print(
        f"[square_post_ext] API request: {endpoint}"
    )

    response = requests.post(
        f"{base_url}{endpoint}",
        json=body,
        headers=headers,
        timeout=30,
    )

    # Binance can return 504 even when the post
    # was actually accepted.
    if (
        endpoint == "/content/add"
        and response.status_code == 504
    ):
        return {
            "id": None,
            "shareLink": None,
            "publishStatus": (
                "success_without_post_id"
            ),
        }

    try:
        data = response.json()

    except ValueError as err:
        raise RuntimeError(
            "API returned non-JSON response: "
            f"{response.status_code} "
            f"{response.reason}"
        ) from err

    if data.get("code") != "000000":
        raise RuntimeError(
            f"API error [{data.get('code')}]: "
            f"{data.get('message')}"
        )

    return data.get("data", {})


def _upload_to_s3(
    presigned_url: str,
    file_path: str,
    content_type: str,
) -> None:
    """
    Upload raw image bytes to Binance-provided
    presigned S3 URL.
    """

    with open(file_path, "rb") as file:
        file_bytes = file.read()

    response = requests.put(
        presigned_url,
        data=file_bytes,
        headers={
            "Content-Type": content_type,
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            "S3 upload failed: "
            f"{response.status_code} "
            f"{response.reason}"
        )


def _poll_image_status(
    api_key: str,
    file_ticket: str,
) -> dict:
    """
    Wait until Binance finishes processing
    the uploaded image.
    """

    for attempt in range(MAX_POLL_RETRIES):

        data = _api(
            "/image/imageStatus",
            api_key,
            {
                "fileTicket": file_ticket,
            },
        )

        status = data.get("status")

        if status == 1:
            return data

        if status == 2:
            raise RuntimeError(
                "Image processing failed: "
                f"{data.get('failedReason')}"
            )

        print(
            "[square_post_ext] "
            f"image processing... "
            f"({attempt + 1}/{MAX_POLL_RETRIES})"
        )

        time.sleep(
            POLL_INTERVAL_SECONDS
        )

    raise RuntimeError(
        "Image processing poll timed out after "
        f"{MAX_POLL_RETRIES} retries."
    )


def post_text_v2(text: str) -> dict:
    """
    Publish a text-only Binance Square post.
    """

    api_key = config.BINANCE_SQUARE_OPENAPI_KEY

    if not api_key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY "
            "is not set in environment."
        )

    text = str(text or "").strip()

    if not text:
        raise ValueError(
            "Refusing to publish an empty post."
        )

    if len(text) > config.CHAR_LIMIT:
        raise ValueError(
            f"Post text is {len(text)} chars, "
            f"over the {config.CHAR_LIMIT} limit."
        )

    print(
        f"[square_post_ext] "
        f"text length: {len(text)}"
    )

    payload = {
        "bodyTextOnly": text,
    }

    data = _api(
        "/content/add",
        api_key,
        payload,
        BASE_URL_V1,
    )

    post_id = data.get("id")

    link = (
        f"https://www.binance.com/en/square/post/"
        f"{post_id}"
        if post_id
        else None
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": (
            data.get("publishStatus")
            == "success_without_post_id"
        ),
    }


def upload_image(
    api_key: str,
    image_path: str,
) -> str:
    """
    Upload an image and return Binance image URL.
    """

    content_type = _get_content_type(
        image_path
    )

    image_name = image_path.rsplit(
        "/",
        1,
    )[-1]

    print(
        f"[square_post_ext] "
        f"uploading image: {image_name}"
    )

    # Step 1:
    # Get presigned upload URL.
    presigned = _api(
        "/image/presignedUrl",
        api_key,
        {
            "imageName": image_name,
        },
    )

    presigned_url = presigned.get(
        "presignedUrl"
    )

    file_ticket = presigned.get(
        "fileTicket"
    )

    if not presigned_url:
        raise RuntimeError(
            "Binance did not return "
            "presignedUrl."
        )

    if not file_ticket:
        raise RuntimeError(
            "Binance did not return "
            "fileTicket."
        )

    # Step 2:
    # Upload image bytes.
    _upload_to_s3(
        presigned_url,
        image_path,
        content_type,
    )

    print(
        "[square_post_ext] "
        "image uploaded to S3."
    )

    # Step 3:
    # Wait for Binance processing.
    status = _poll_image_status(
        api_key,
        file_ticket,
    )

    image_url = status.get(
        "imageUrl"
    )

    if not image_url:
        raise RuntimeError(
            "Binance image processing completed "
            "but imageUrl was empty."
        )

    print(
        "[square_post_ext] "
        f"image ready: {image_url}"
    )

    return image_url


def post_with_images(
    text: str,
    image_paths: list[str],
) -> dict:
    """
    Publish a Binance Square post with
    text and 1-4 images.
    """

    api_key = config.BINANCE_SQUARE_OPENAPI_KEY

    if not api_key:
        raise RuntimeError(
            "BINANCE_SQUARE_OPENAPI_KEY "
            "is not set in environment."
        )

    # -------------------------------------------------
    # Validate text
    # -------------------------------------------------

    text = str(text or "").strip()

    if not text:
        raise ValueError(
            "Refusing to publish an empty post."
        )

    if len(text) > config.CHAR_LIMIT:
        raise ValueError(
            f"Post text is {len(text)} chars, "
            f"over the {config.CHAR_LIMIT} limit."
        )

    # -------------------------------------------------
    # Validate images
    # -------------------------------------------------

    if not image_paths:
        raise ValueError(
            "post_with_images requires "
            "at least 1 image."
        )

    if len(image_paths) > 4:
        raise ValueError(
            "post_with_images supports "
            "maximum 4 images."
        )

    print(
        "[square_post_ext] "
        f"post text length: {len(text)}"
    )

    print(
        "[square_post_ext] "
        f"image count: {len(image_paths)}"
    )

    # -------------------------------------------------
    # Upload images
    # -------------------------------------------------

    image_urls = []

    for image_path in image_paths:

        image_url = upload_image(
            api_key,
            image_path,
        )

        if not image_url:
            raise RuntimeError(
                f"Image URL is empty for: "
                f"{image_path}"
            )

        image_urls.append(
            image_url
        )

    print(
        "[square_post_ext] "
        f"uploaded images: {len(image_urls)}"
    )

    # -------------------------------------------------
    # Publish post
    # -------------------------------------------------

    payload = {
        # Keep both fields populated.
        # bodyTextOnly preserves the text content
        # expected by the Square OpenAPI.
        "bodyTextOnly": text,

        # Main post content.
        "content": text,

        # 1 = image post.
        "contentType": 1,

        # Binance image URLs.
        "imageList": image_urls,
    }

    print(
        "[square_post_ext] "
        "publishing post..."
    )

    data = _api(
        "/content/add",
        api_key,
        payload,
        BASE_URL_V1,
    )

    post_id = data.get("id")

    link = (
        f"https://www.binance.com/en/square/post/"
        f"{post_id}"
        if post_id
        else None
    )

    soft_success = (
        data.get("publishStatus")
        == "success_without_post_id"
    )

    print(
        "[square_post_ext] "
        f"publish response: "
        f"id={post_id}, "
        f"soft_success={soft_success}"
    )

    return {
        "id": post_id,
        "link": link,
        "soft_success": soft_success,
    }
