import asyncio
import logging
import requests

import config

logger = logging.getLogger(__name__)

_BING_ENDPOINT = "https://ssl.bing.com/webmaster/api.svc/json/SubmitUrl"


async def submit_to_bing(url: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _submit_sync, url)


def _submit_sync(url: str) -> bool:
    if not config.BING_API_KEY:
        logger.warning("Bing API 키가 설정되지 않았습니다.")
        return False
    try:
        resp = requests.post(
            _BING_ENDPOINT,
            params={"apikey": config.BING_API_KEY},
            json={"siteUrl": config.WP_URL, "url": url},
            timeout=15,
        )
        resp.raise_for_status()
        logger.info("Bing Indexing 성공: %s", url)
        return True
    except Exception as e:
        logger.error("Bing Indexing 실패: %s", e)
        return False
