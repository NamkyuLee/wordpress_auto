import asyncio
import logging
import requests

import config

logger = logging.getLogger(__name__)

# 네이버 서치어드바이저는 공개 URL 제출 API가 없으므로
# 사이트맵 핑 방식으로 크롤링 요청
_NAVER_PING_ENDPOINT = "https://searchadvisor.naver.com/ping"


async def submit_to_naver(url: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _submit_sync, url)


def _submit_sync(url: str) -> bool:
    sitemap_url = f"{config.WP_URL}/sitemap_index.xml"
    try:
        resp = requests.get(
            _NAVER_PING_ENDPOINT,
            params={"sitemap": sitemap_url},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Naver 사이트맵 핑 성공: %s", sitemap_url)
        return True
    except Exception as e:
        logger.error("Naver 사이트맵 핑 실패: %s", e)
        return False
