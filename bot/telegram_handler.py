import asyncio
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config
from ai.content_generator import generate_content, generate_writing_suggestion
from ai.reference_fetcher import fetch_reference_url, fetch_references_from_text
from wordpress.publisher import publish_post
from seo.google_index import submit_to_google
from seo.bing_index import submit_to_bing
from seo.naver_index import submit_to_naver
from social.x_promo import build_x_promo, build_x_intent_url
from social.x_poster import post_to_x

logger = logging.getLogger(__name__)

_ALBUM_WAIT = 1.5  # 앨범 묶음 수집 대기 시간(초)
_pending_albums: dict[str, dict] = {}  # media_group_id → {bot, chat_id, topic, file_ids, task}

_HELP_TEXT = """안녕하세요! 블로그 자동화 봇입니다.

글 작성 흐름
1. 주제만 보내면 글을 생성해 워드프레스에 업로드합니다.
2. "OO에 대한 글을 쓰고 싶어"처럼 보내면 먼저 작성 요청서를 제안합니다.
3. 제안서가 마음에 들면 그대로 다시 보내면 글 작성으로 들어갑니다.

자주 쓰는 입력 예시
/suggest Polymarket 예측시장 입문 글

/postx https://bullswave.com/example-post/

제안: Polymarket 예측시장 입문 글

Polymarket에 대한 글을 쓰고 싶어

[주제]
Polymarket 예측시장 입문

[독자]
Polymarket을 처음 접한 한국 독자

[주의사항]
투자 권유처럼 쓰지 말고 구조와 리스크 중심으로 설명

사진/URL 사용
- 사진은 한 장 또는 여러 장 앨범으로 보내도 됩니다.
- 사진 캡션에 주제를 적으면 사진을 참고해서 글을 씁니다.
- 기사나 참고 URL을 같이 보내면 내용을 가져와 참고자료로 반영합니다.

X 홍보
- 글 업로드가 끝나면 X에 복사해 올릴 짧은 홍보 문구도 함께 보여줍니다.
- X_AUTO_POST=true와 API 키가 설정되어 있으면 공개 글은 X에도 자동 게시합니다.
- 공개 글은 URL 카드가 뜨도록 featured image와 Rank Math 메타를 확인하세요.
- X 인증 실패가 나오면 X Developer Portal에서 Read and write 권한으로 Access Token/Secret을 재발급하세요.

예:
Polymarket 예측시장 구조를 설명하는 글 써줘.
https://example.com/article

참고
- /start 또는 /help를 입력하면 이 안내를 다시 볼 수 있습니다.
- 기본 설정이 draft라면 워드프레스 초안으로 올라가고, 공개 글만 검색엔진 등록을 시도합니다."""


def _is_allowed(user_id: int) -> bool:
    return config.ALLOWED_USER_ID == 0 or user_id == config.ALLOWED_USER_ID


def _status_icon(value: bool | None) -> str:
    if value is None:
        return "건너뜀"
    return "✅" if value else "❌"


def _looks_like_suggestion_request(text: str) -> bool:
    if "[주제]" in text or "[독자]" in text:
        return False

    patterns = (
        "글을 쓰고 싶",
        "글 쓰고 싶",
        "포스팅하고 싶",
        "포스팅을 하고 싶",
        "작성하고 싶",
        "주제로 글",
    )
    return any(pattern in text for pattern in patterns)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(_HELP_TEXT)


async def suggest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    topic = " ".join(context.args).strip()
    if not topic:
        await update.message.reply_text("예: /suggest Polymarket 예측시장 입문 글")
        return

    await _run_suggestion(update.message, topic)


async def postx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    post_url = " ".join(context.args).strip()
    if not post_url:
        await update.message.reply_text("예: /postx https://bullswave.com/example-post/")
        return

    status_msg = await update.message.reply_text("X 홍보 문구를 준비 중입니다...")
    try:
        reference = await fetch_reference_url(post_url)
        content = {
            "title": reference.get("title", "") if reference else "",
            "meta_description": reference.get("description", "") if reference else "",
            "tags": [],
        }
        x_promo = build_x_promo(content, post_url)
        x_intent_url = build_x_intent_url(x_promo)
        x_posted, x_post_result = await post_to_x(x_promo)
        if x_posted:
            x_line = f"X 자동 게시: ✅ {x_post_result}"
        else:
            x_line = f"X 게시: {x_post_result}\n👉 {x_intent_url}"
        await status_msg.edit_text(
            f"{x_line}\n\n"
            f"X 홍보 문구:\n{x_promo}"
        )
    except Exception as e:
        logger.exception("X post error")
        await status_msg.edit_text(f"❌ X 홍보 처리 오류: {e}")


async def _flush_album(group_id: str) -> None:
    await asyncio.sleep(_ALBUM_WAIT)
    album = _pending_albums.pop(group_id, None)
    if not album:
        return
    await _run_pipeline(album["bot"], album["chat_id"], album["topic"], album["file_ids"])


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    message = update.message
    topic = message.caption or "사진을 보고 블로그 글 작성"
    file_id = message.photo[-1].file_id
    group_id = message.media_group_id

    if group_id:
        if group_id in _pending_albums:
            _pending_albums[group_id]["file_ids"].append(file_id)
            if message.caption:
                _pending_albums[group_id]["topic"] = topic
        else:
            task = asyncio.create_task(_flush_album(group_id))
            _pending_albums[group_id] = {
                "bot": context.bot,
                "chat_id": message.chat_id,
                "topic": topic,
                "file_ids": [file_id],
                "task": task,
            }
    else:
        await _run_pipeline(context.bot, message.chat_id, topic, [file_id])


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    topic = update.message.text.strip()
    if not topic:
        return

    suggestion_prefixes = ("제안:", "제안：", "suggest:", "Suggest:")
    for prefix in suggestion_prefixes:
        if topic.startswith(prefix):
            suggested_topic = topic[len(prefix):].strip()
            if not suggested_topic:
                await update.message.reply_text("예: 제안: Polymarket 예측시장 입문 글")
                return
            await _run_suggestion(update.message, suggested_topic)
            return

    if topic.startswith("제안 "):
        suggested_topic = topic[len("제안 "):].strip()
        if not suggested_topic:
            await update.message.reply_text("예: 제안 Polymarket 예측시장 입문 글")
            return
        await _run_suggestion(update.message, suggested_topic)
        return

    if _looks_like_suggestion_request(topic):
        await _run_suggestion(update.message, topic)
        return

    await _run_pipeline(context.bot, update.message.chat_id, topic, [])


async def _run_suggestion(message, topic: str) -> None:
    status_msg = await message.reply_text("🧭 작성 요청서를 제안 중입니다...")
    try:
        references = await fetch_references_from_text(topic)
        suggestion = await generate_writing_suggestion(topic, references)
        notes = suggestion.get("notes", [])
        notes_text = "\n".join(f"- {note}" for note in notes)
        result = suggestion["suggested_prompt"]
        if notes_text:
            result = f"{result}\n\n[보완 팁]\n{notes_text}"
        await status_msg.edit_text(result)
    except Exception as e:
        logger.exception("Suggestion error")
        await status_msg.edit_text(f"❌ 제안 생성 오류: {e}")


async def _run_pipeline(bot, chat_id: int, topic: str, photo_file_ids: list) -> None:
    status_msg = await bot.send_message(chat_id, "✍️ 블로그 글을 작성 중입니다...")

    try:
        # 사진 다운로드 (bytes)
        images_bytes = []
        for fid in photo_file_ids:
            tg_file = await bot.get_file(fid)
            data = await tg_file.download_as_bytearray()
            images_bytes.append(bytes(data))

        references = await fetch_references_from_text(topic)
        if references:
            await bot.edit_message_text(
                f"🔗 참고 URL {len(references)}개를 반영해 AI가 글을 생성 중입니다...",
                chat_id,
                status_msg.message_id,
            )
        else:
            await bot.edit_message_text("🤖 AI가 글을 생성 중입니다...", chat_id, status_msg.message_id)

        content = await generate_content(topic, images_bytes, references)

        await bot.edit_message_text("📤 워드프레스에 업로드 중입니다...", chat_id, status_msg.message_id)
        post = await publish_post(content, images_bytes)
        post_url = post["link"]

        if post["status"] == "publish":
            await bot.edit_message_text("🔍 검색엔진에 등록 중입니다...", chat_id, status_msg.message_id)
            google_ok = await submit_to_google(post_url)
            bing_ok = await submit_to_bing(post_url)
            naver_ok = await submit_to_naver(post_url)
        else:
            google_ok = bing_ok = naver_ok = None

        x_promo = build_x_promo(content, post_url)
        x_intent_url = build_x_intent_url(x_promo)
        if post["status"] == "publish":
            x_posted, x_post_result = await post_to_x(x_promo)
        else:
            x_posted, x_post_result = False, "초안 상태라 자동 게시하지 않음"

        if x_posted:
            x_line = f"X 자동 게시: ✅ {x_post_result}"
        else:
            x_line = f"X 게시: {x_post_result}\n👉 {x_intent_url}"

        result = (
            f"✅ 워드프레스 업로드 완료!\n\n"
            f"🔗 URL: {post_url}\n\n"
            f"상태: {post['status']}\n"
            f"카테고리: {', '.join(post['categories']) or '없음'}\n"
            f"태그: {', '.join(post['tags']) or '없음'}\n"
            f"참고 URL: {len(references)}개\n\n"
            f"검색엔진 등록:\n"
            f"  • Google: {'사이트맵 자동등록' if google_ok is None else _status_icon(google_ok)}\n"
            f"  • Bing: {_status_icon(bing_ok)}\n"
            f"  • 네이버: {_status_icon(naver_ok)}\n\n"
            f"{x_line}\n\n"
            f"X 홍보 문구:\n{x_promo}"
        )
        await bot.edit_message_text(result, chat_id, status_msg.message_id)

    except Exception as e:
        logger.exception("Pipeline error")
        await bot.edit_message_text(f"❌ 오류 발생: {e}", chat_id, status_msg.message_id)


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", start))
    app.add_handler(CommandHandler("suggest", suggest))
    app.add_handler(CommandHandler("postx", postx))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
