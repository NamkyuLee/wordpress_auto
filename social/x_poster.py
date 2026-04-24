import logging
import asyncio

import config

logger = logging.getLogger(__name__)


def is_x_posting_configured() -> bool:
    return all(
        [
            config.X_API_KEY,
            config.X_API_SECRET,
            config.X_ACCESS_TOKEN,
            config.X_ACCESS_TOKEN_SECRET,
        ]
    )


async def post_to_x(text: str) -> tuple[bool, str]:
    if not config.X_AUTO_POST:
        return False, "X_AUTO_POST=false"

    if not is_x_posting_configured():
        return False, "X API 키가 설정되지 않았습니다"

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _post_to_x_sync, text)


def _post_to_x_sync(text: str) -> tuple[bool, str]:
    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=config.X_API_KEY,
            consumer_secret=config.X_API_SECRET,
            access_token=config.X_ACCESS_TOKEN,
            access_token_secret=config.X_ACCESS_TOKEN_SECRET,
        )
        response = client.create_tweet(text=text, user_auth=True)
        tweet_id = response.data.get("id") if response.data else None
        if not tweet_id:
            return False, "X 응답에 tweet id가 없습니다"
        logger.info("X 게시 성공: %s", tweet_id)
        return True, f"https://x.com/i/web/status/{tweet_id}"
    except ImportError:
        return False, "tweepy가 설치되지 않았습니다. pip install -r requirements.txt를 실행하세요"
    except Exception as exc:
        logger.exception("X 게시 실패")
        return False, _format_x_error(exc)


def _format_x_error(exc: Exception) -> str:
    message = str(exc)
    if "401" in message or "Unauthorized" in message or "Invalid or expired token" in message:
        return (
            "X 인증 실패: Access Token/Secret이 만료됐거나 API Key/Secret과 맞지 않습니다. "
            "X Developer Portal에서 Read and write 권한으로 Access Token/Secret을 재발급하세요."
        )
    if "403" in message or "Forbidden" in message:
        return "X 권한 실패: 앱 권한이 Read and write인지 확인하고 토큰을 재발급하세요."
    if "429" in message or "Too Many Requests" in message:
        return "X 요청 제한에 걸렸습니다. 잠시 후 다시 시도하세요."
    return message
