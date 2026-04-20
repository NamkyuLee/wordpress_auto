import logging
from bot.telegram_handler import build_application

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)

if __name__ == "__main__":
    app = build_application()
    app.run_polling(drop_pending_updates=True)
