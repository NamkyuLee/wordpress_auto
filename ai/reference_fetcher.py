import asyncio
import html
import logging
import re
from urllib.parse import urlparse, parse_qs

import requests

import config

logger = logging.getLogger(__name__)

_URL_RE = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style|noscript|svg|iframe)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def extract_urls(text: str) -> list[str]:
    urls = []
    seen = set()
    for match in _URL_RE.finditer(text or ""):
        url = match.group(0).rstrip(".,;:!?)]}>\u3002")
        key = url.casefold()
        if key in seen:
            continue
        urls.append(url)
        seen.add(key)
        if len(urls) >= config.REFERENCE_MAX_URLS:
            break
    return urls


async def fetch_references_from_text(text: str) -> list[dict]:
    urls = extract_urls(text)
    if not urls:
        return []

    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, _fetch_reference, url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [result for result in results if result]


async def fetch_reference_url(url: str) -> dict | None:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_reference, url)


def _extract_youtube_id(url: str) -> str | None:
    parsed = urlparse(url)
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            return parts[1]
        qs = parse_qs(parsed.query)
        vid = qs.get("v", [None])[0]
        return vid
    if parsed.hostname in ("youtu.be",):
        return parsed.path.lstrip("/").split("?")[0] or None
    return None


def _fetch_youtube(url: str, video_id: str) -> dict | None:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled, VideoUnavailable
    except ImportError:
        logger.warning("youtube-transcript-api 미설치 — 일반 HTML 방식으로 폴백")
        return None

    # 영상 제목/설명은 페이지 HTML에서 추출
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        page = resp.content.decode(resp.encoding or "utf-8", errors="replace")
        title = _extract_title(page) or f"YouTube 영상 ({video_id})"
        description = _extract_meta_description(page)
    except Exception:
        title = f"YouTube 영상 ({video_id})"
        description = ""

    transcript_text = ""
    try:
        api = YouTubeTranscriptApi()
        transcript_list = api.list(video_id)
        try:
            transcript = transcript_list.find_transcript(["ko", "en"])
        except NoTranscriptFound:
            transcript = transcript_list.find_generated_transcript(["ko", "en"])
        entries = transcript.fetch()
        transcript_text = " ".join(
            e.text if hasattr(e, "text") else e.get("text", "")
            for e in entries
        )
        transcript_text = transcript_text[:config.REFERENCE_MAX_CHARS]
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable) as e:
        logger.info("YouTube 자막 없음 (%s): %s", video_id, e)
    except Exception as e:
        logger.warning("YouTube 자막 추출 실패 (%s): %s", video_id, e)

    return {
        "url": url,
        "title": title,
        "description": description,
        "text": transcript_text if transcript_text else "자막을 가져올 수 없는 영상입니다.",
    }


def _fetch_reference(url: str) -> dict | None:
    video_id = _extract_youtube_id(url)
    if video_id:
        result = _fetch_youtube(url, video_id)
        if result:
            return result

    try:
        resp = requests.get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; WordpressAutoBot/1.0; "
                    "+https://bullswave.com)"
                )
            },
            timeout=12,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type.lower():
            return {
                "url": url,
                "title": _fallback_title(url),
                "description": f"HTML 문서가 아닌 참고 URL입니다. Content-Type: {content_type or 'unknown'}",
                "text": "",
            }

        encoding = resp.encoding or resp.apparent_encoding or "utf-8"
        page = resp.content.decode(encoding, errors="replace")
        title = _extract_title(page) or _fallback_title(url)
        description = _extract_meta_description(page)
        text = _extract_visible_text(page)
        return {
            "url": url,
            "title": title,
            "description": description,
            "text": text[:config.REFERENCE_MAX_CHARS],
        }
    except Exception as exc:
        logger.warning("참고 URL 가져오기 실패: %s (%s)", url, exc)
        return {
            "url": url,
            "title": _fallback_title(url),
            "description": f"참고 URL 내용을 가져오지 못했습니다: {exc}",
            "text": "",
        }


def _extract_title(page: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return _normalize_text(match.group(1))


def _extract_meta_description(page: str) -> str:
    patterns = (
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:description["\']',
    )
    for pattern in patterns:
        match = re.search(pattern, page, re.IGNORECASE | re.DOTALL)
        if match:
            return _normalize_text(match.group(1))
    return ""


def _extract_visible_text(page: str) -> str:
    page = _SCRIPT_STYLE_RE.sub(" ", page)
    page = re.sub(r"</(p|div|li|h[1-6]|tr|section|article)>", "\n", page, flags=re.IGNORECASE)
    text = _TAG_RE.sub(" ", page)
    return _normalize_text(text)


def _normalize_text(value: str) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _fallback_title(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc or url
