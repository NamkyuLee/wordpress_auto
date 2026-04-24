import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = int(os.environ.get("ALLOWED_TELEGRAM_USER_ID", "0"))

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

WP_URL = os.environ["WP_URL"].rstrip("/")
WP_USERNAME = os.environ["WP_USERNAME"]
WP_APP_PASSWORD = os.environ["WP_APP_PASSWORD"]

GOOGLE_SERVICE_ACCOUNT_JSON = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "./google_service_account.json")

BING_API_KEY = os.environ.get("BING_API_KEY", "")

SITE_FOCUS = os.environ.get(
    "SITE_FOCUS",
    "독자가 직접 의사결정에 활용할 수 있는 한국어 정보형 블로그",
)

WP_POST_STATUS = os.environ.get("WP_POST_STATUS", "draft").strip().lower()
if WP_POST_STATUS not in {"draft", "publish"}:
    WP_POST_STATUS = "draft"

WP_ALLOWED_CATEGORIES = [
    category.strip()
    for category in os.environ.get("WP_ALLOWED_CATEGORIES", "Life Trend,IT Trend").split(",")
    if category.strip()
]
WP_DEFAULT_CATEGORY = os.environ.get(
    "WP_DEFAULT_CATEGORY",
    WP_ALLOWED_CATEGORIES[0] if WP_ALLOWED_CATEGORIES else "Life Trend",
).strip()

try:
    WP_MAX_TAGS = int(os.environ.get("WP_MAX_TAGS", "3"))
except ValueError:
    WP_MAX_TAGS = 3
WP_MAX_TAGS = max(0, WP_MAX_TAGS)
WP_CREATE_MISSING_TAGS = os.environ.get("WP_CREATE_MISSING_TAGS", "false").lower() == "true"

GOOGLE_INDEXING_ENABLED = os.environ.get("GOOGLE_INDEXING_ENABLED", "false").lower() == "true"

NAVER_INDEXNOW_KEY = os.environ.get("NAVER_INDEXNOW_KEY", "")
NAVER_INDEXNOW_KEY_LOCATION = os.environ.get("NAVER_INDEXNOW_KEY_LOCATION", "")

try:
    REFERENCE_MAX_URLS = int(os.environ.get("REFERENCE_MAX_URLS", "3"))
except ValueError:
    REFERENCE_MAX_URLS = 3
REFERENCE_MAX_URLS = max(0, REFERENCE_MAX_URLS)

try:
    REFERENCE_MAX_CHARS = int(os.environ.get("REFERENCE_MAX_CHARS", "3500"))
except ValueError:
    REFERENCE_MAX_CHARS = 3500
REFERENCE_MAX_CHARS = max(500, REFERENCE_MAX_CHARS)

X_AUTO_POST = os.environ.get("X_AUTO_POST", "false").lower() == "true"
X_API_KEY = os.environ.get("X_API_KEY", "")
X_API_SECRET = os.environ.get("X_API_SECRET", "")
X_ACCESS_TOKEN = os.environ.get("X_ACCESS_TOKEN", "")
X_ACCESS_TOKEN_SECRET = os.environ.get("X_ACCESS_TOKEN_SECRET", "")
