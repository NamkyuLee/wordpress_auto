import asyncio
import mimetypes
from typing import Any

import requests
from requests.auth import HTTPBasicAuth

import config

_auth = HTTPBasicAuth(config.WP_USERNAME, config.WP_APP_PASSWORD)
_headers = {"Accept": "application/json"}


def _api(path: str) -> str:
    return f"{config.WP_URL}/wp-json/wp/v2/{path}"


def _upload_image(image_bytes: bytes, filename: str = "photo.jpg", alt_text: str = "") -> int:
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
    media_id = resp.json()["id"]
    if alt_text:
        requests.post(
            _api(f"media/{media_id}"),
            auth=_auth,
            json={"alt_text": alt_text},
            timeout=15,
        )
    return media_id


def _clean_term_names(names: list[str], max_items: int | None = None) -> list[str]:
    if max_items == 0:
        return []

    cleaned = []
    seen = set()
    for name in names:
        normalized = " ".join(str(name).strip().split())
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        cleaned.append(normalized)
        seen.add(key)
        if max_items is not None and len(cleaned) >= max_items:
            break
    return cleaned


def _filter_allowed_categories(names: list[str]) -> list[str]:
    allowed = config.WP_ALLOWED_CATEGORIES
    if not allowed:
        return _clean_term_names(names)

    allowed_by_key = {name.casefold(): name for name in allowed}
    filtered = []
    for name in _clean_term_names(names):
        allowed_name = allowed_by_key.get(name.casefold())
        if allowed_name:
            filtered.append(allowed_name)

    return filtered or [config.WP_DEFAULT_CATEGORY]


def _find_term(endpoint: str, name: str) -> dict[str, Any] | None:
    search = requests.get(_api(endpoint), auth=_auth, params={"search": name}, timeout=15)
    search.raise_for_status()
    results = search.json()
    for result in results:
        if result.get("name", "").casefold() == name.casefold():
            return result
    return None


def _get_or_create_terms(endpoint: str, names: list[str], create_missing: bool = True) -> list[int]:
    ids = []
    for name in _clean_term_names(names):
        existing = _find_term(endpoint, name)
        if existing:
            ids.append(existing["id"])
        elif create_missing:
            create = requests.post(_api(endpoint), auth=_auth,
                                   json={"name": name}, timeout=15)
            create.raise_for_status()
            ids.append(create.json()["id"])
    return ids


async def publish_post(content: dict, images_bytes: list[bytes]) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _publish_sync, content, images_bytes)


def _publish_sync(content: dict, images_bytes: list[bytes]) -> dict:
    alt_text = content.get("focus_keyword") or content.get("title", "")
    featured_media = 0
    if images_bytes:
        featured_media = _upload_image(images_bytes[0], "featured.jpg", alt_text=alt_text)

    category_names = _filter_allowed_categories(content.get("categories") or [])
    tag_names = _clean_term_names(content.get("tags") or [], max_items=config.WP_MAX_TAGS)

    category_ids = _get_or_create_terms("categories", category_names, create_missing=True)
    tag_ids = _get_or_create_terms(
        "tags",
        tag_names,
        create_missing=config.WP_CREATE_MISSING_TAGS,
    )

    rank_math_meta = {
        "rank_math_title": content["title"],
        "rank_math_description": content.get("meta_description", ""),
        "rank_math_focus_keyword": content.get("focus_keyword", ""),
        "rank_math_og_title": content["title"],
        "rank_math_og_description": content.get("meta_description", ""),
        "rank_math_twitter_title": content["title"],
        "rank_math_twitter_description": content.get("meta_description", ""),
    }
    if config.WP_POST_STATUS == "publish":
        rank_math_meta["rank_math_robots"] = ["index", "follow"]

    post_data = {
        "title": content["title"],
        "content": content["content"],
        "slug": content.get("slug", ""),
        "status": config.WP_POST_STATUS,
        "categories": category_ids,
        "tags": tag_ids,
        "meta": rank_math_meta,
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
    result = resp.json()
    return {
        "link": result["link"],
        "status": result.get("status", config.WP_POST_STATUS),
        "categories": category_names,
        "tags": tag_names,
    }
