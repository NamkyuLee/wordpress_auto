import asyncio
import logging

import config

logger = logging.getLogger(__name__)


async def submit_to_google(url: str) -> bool:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _submit_sync, url)


def _submit_sync(url: str) -> bool:
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_JSON,
            scopes=["https://www.googleapis.com/auth/indexing"],
        )
        service = build("indexing", "v3", credentials=creds, cache_discovery=False)
        body = {"url": url, "type": "URL_UPDATED"}
        service.urlNotifications().publish(body=body).execute()
        logger.info("Google Indexing 성공: %s", url)
        return True
    except Exception as e:
        logger.error("Google Indexing 실패: %s", e)
        return False
