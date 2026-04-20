import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

import config
from ai.content_generator import generate_content
from wordpress.publisher import publish_post
from seo.google_index import submit_to_google
from seo.bing_index import submit_to_bing
from seo.naver_index import submit_to_naver

logger = logging.getLogger(__name__)


def _is_allowed(user_id: int) -> bool:
    return config.ALLOWED_USER_ID == 0 or user_id == config.ALLOWED_USER_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "안녕하세요! 블로그 자동화 봇입니다.\n"
        "주제 텍스트를 보내거나, 사진과 함께 주제를 캡션으로 전송하세요."
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    message = update.message
    topic = message.caption or "사진을 보고 블로그 글 작성"
    photo_file_ids = [message.photo[-1].file_id]

    await _run_pipeline(context.bot, message.chat_id, topic, photo_file_ids)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_allowed(update.effective_user.id):
        return

    topic = update.message.text.strip()
    if not topic:
        return

    await _run_pipeline(context.bot, update.message.chat_id, topic, [])


async def _run_pipeline(bot, chat_id: int, topic: str, photo_file_ids: list) -> None:
    status_msg = await bot.send_message(chat_id, "✍️ 블로그 글을 작성 중입니다...")

    try:
        # 사진 다운로드 (bytes)
        images_bytes = []
        for fid in photo_file_ids:
            tg_file = await bot.get_file(fid)
            data = await tg_file.download_as_bytearray()
            images_bytes.append(bytes(data))

        await bot.edit_message_text("🤖 AI가 글을 생성 중입니다...", chat_id, status_msg.message_id)
        content = await generate_content(topic, images_bytes)

        await bot.edit_message_text("📤 워드프레스에 업로드 중입니다...", chat_id, status_msg.message_id)
        post_url = await publish_post(content, images_bytes)

        await bot.edit_message_text("🔍 검색엔진에 등록 중입니다...", chat_id, status_msg.message_id)
        google_ok = await submit_to_google(post_url)
        bing_ok = await submit_to_bing(post_url)
        naver_ok = await submit_to_naver(post_url)

        result = (
            f"✅ 게시 완료!\n\n"
            f"🔗 URL: {post_url}\n\n"
            f"검색엔진 등록:\n"
            f"  • Google: {'✅' if google_ok else '❌'}\n"
            f"  • Bing: {'✅' if bing_ok else '❌'}\n"
            f"  • 네이버: {'✅' if naver_ok else '❌'}"
        )
        await bot.edit_message_text(result, chat_id, status_msg.message_id)

    except Exception as e:
        logger.exception("Pipeline error")
        await bot.edit_message_text(f"❌ 오류 발생: {e}", chat_id, status_msg.message_id)


def build_application() -> Application:
    app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return app
