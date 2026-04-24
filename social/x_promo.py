import re
from urllib.parse import quote

_MAX_X_CHARS = 200
_URL_RESERVED_CHARS = 23


def build_x_promo(content: dict, post_url: str) -> str:
    title = _clean_text(content.get("title", ""))
    description = _clean_text(content.get("meta_description", ""))
    hashtags = _build_hashtags(content)

    fixed_parts = [title, "블로그에 정리했습니다.", post_url]
    if hashtags:
        fixed_parts.append(hashtags)

    fixed_text = "\n".join(part for part in fixed_parts if part)
    description_budget = max(0, _MAX_X_CHARS - _tweet_length(fixed_text) - 1)
    description = _truncate(description, description_budget)

    parts = [title]
    if description:
        parts.append(description)
    parts.extend(["블로그에 정리했습니다.", post_url])
    if hashtags:
        parts.append(hashtags)

    return "\n".join(parts).strip()


def build_x_intent_url(x_promo_text: str) -> str:
    return f"https://x.com/intent/tweet?text={quote(x_promo_text)}"


def _build_hashtags(content: dict) -> str:
    candidates = []
    for tag in content.get("tags") or []:
        candidates.append(str(tag))
    if content.get("focus_keyword"):
        candidates.append(str(content["focus_keyword"]))

    hashtags = []
    seen = set()
    for candidate in candidates:
        tag = _hashtag(candidate)
        key = tag.casefold()
        if not tag or key in seen:
            continue
        hashtags.append(tag)
        seen.add(key)
        if len(hashtags) >= 3:
            break
    return " ".join(hashtags)


def _hashtag(value: str) -> str:
    value = re.sub(r"\s+", "", _clean_text(value))
    value = re.sub(r"[^\w가-힣]", "", value)
    if not value:
        return ""
    return f"#{value}"


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def _tweet_length(value: str) -> int:
    # X counts most URLs as a fixed length. This approximation is enough for copy suggestions.
    return len(re.sub(r"https?://\S+", "x" * _URL_RESERVED_CHARS, value))
