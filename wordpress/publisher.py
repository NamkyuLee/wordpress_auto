import asyncio
import mimetypes
import requests
from requests.auth import HTTPBasicAuth

import config

_auth = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
_headers = {"Accept": "application/json"}


def _api(path: str) -> str:
    return f"{config.WP_URL}/wp-json/wp/v2/{path}"


def _upload_image(image_bytes: bytes, filename: str = "photo.jpg") -> int:
    mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
    resp = requests.post(
        _api("media"),
        auth=_auth,
        headers={"Content-Disposition": f'attachment; filename="{filename}"',
                 "Content-Type": mime},
        data=image_bytes,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def _get_or_create_terms(endpoint: str, names: list[str]) -> list[int]:
    ids = []
    for name in names:
        search = requests.get(_api(endpoint), auth=_auth,
                              params={"search": name}, timeout=15)
        search.raise_for_status()
        results = search.json()
        if results:
            ids.append(results[0]["id"])
        else:
            create = requests.post(_api(endpoint), auth=_auth,
                                   json={"name": name}, timeout=15)
            create.raise_for_status()
            ids.append(create.json()["id"])
    return ids


async def publish_post(content: dict, images_bytes: list[bytes]) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _publish_sync, content, images_bytes)


def _publish_sync(content: dict, images_bytes: list[bytes]) -> str:
    featured_media = 0
    if images_bytes:
        featured_media = _upload_image(images_bytes[0], "featured.jpg")

    category_ids = _get_or_create_terms("categories", content.get("categories", []))
    tag_ids = _get_or_create_terms("tags", content.get("tags", []))

    post_data = {
        "title": content["title"],
        "content": content["content"],
        "slug": content.get("slug", ""),
        "status": "publish",
        "categories": category_ids,
        "tags": tag_ids,
        "meta": {
            "rank_math_title": content["title"],
            "rank_math_description": content.get("meta_description", ""),
            "rank_math_focus_keyword": content.get("focus_keyword", ""),
        },
    }
    if featured_media:
        post_data["featured_media"] = featured_media

    resp = requests.post(
        _api("posts"),
        auth=_auth,
        json=post_data,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["link"]
