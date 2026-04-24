import asyncio
import logging

import requests

import config

logger = logging.getLogger(__name__)

_INDEXNOW_ENDPOINT = "https://searchadvisor.naver.com/indexnow"


async def submit_to_naver(url: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _submit_sync, url)


def _submit_sync(url: str) -> bool:
    if not config.NAVER_INDEXNOW_KEY:
        logger.warning("NAVER_INDEXNOW_KEY 미설정 — 네이버 등록 건너뜀")
        return False

    payload = {
        "host": config.WP_URL.replace("https://", "").replace("http://", "").rstrip("/"),
        "key": config.NAVER_INDEXNOW_KEY,
        "urlList": [url],
    }
    if config.NAVER_INDEXNOW_KEY_LOCATION:
        payload["keyLocation"] = config.NAVER_INDEXNOW_KEY_LOCATION

    try:
        resp = requests.post(
            _INDEXNOW_ENDPOINT,
            json=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=15,
        )
        if resp.status_code in (200, 202):
            logger.info("Naver IndexNow 등록 성공: %s", url)
            return True
        logger.error("Naver IndexNow 등록 실패: HTTP %s %s", resp.status_code, resp.text[:200])
        return False
    except Exception as e:
        logger.error("Naver IndexNow 요청 오류: %s", e)
        return False
