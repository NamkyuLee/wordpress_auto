# WordPress 블로그 자동화 시스템 — 작업 현황

## 개요

텔레그램으로 주제/사진을 전송하면 AI가 블로그 글을 작성하고, 워드프레스에 SEO 설정과 함께 자동 게시한 뒤, Google·Bing·네이버 웹마스터에 URL을 등록하는 자동화 파이프라인.

---

## 전체 흐름

```
텔레그램 (주제 + 사진)
    ↓
Claude AI (제목 / 본문 / SEO 메타데이터 생성)
    ↓
WordPress REST API (포스트 업로드 + Yoast SEO 설정 + 공개)
    ↓
검색엔진 등록 (Google / Bing / 네이버)
    ↓
텔레그램 (결과 보고)
```

---

## 프로젝트 구조

```
wordpress_auto/
├── main.py                      # 진입점 — 텔레그램 봇 실행
├── config.py                    # 환경변수 로드
├── requirements.txt             # Python 의존성
├── .env.example                 # 필요한 키 목록 (참고용)
├── .gitignore
├── bot/
│   └── telegram_handler.py      # 텔레그램 메시지·사진 수신 & 파이프라인 조율
├── ai/
│   └── content_generator.py     # Claude API로 제목/본문/SEO 생성
├── wordpress/
│   └── publisher.py             # WordPress REST API 게시 & 미디어 업로드
└── seo/
    ├── google_index.py          # Google Indexing API 제출
    ├── bing_index.py            # Bing URL Submission API 제출
    └── naver_index.py           # 네이버 서치어드바이저 API 제출
```

---

## 완료된 작업

### Step 1 — 프로젝트 기반 설정
- `requirements.txt` — `python-telegram-bot`, `anthropic`, `requests`, `python-dotenv`, `google-auth`, `google-api-python-client`
- `.env.example` — 필요한 환경변수 키 목록
- `config.py` — 환경변수 로드 모듈
- `.gitignore` — `.env`, 서비스 계정 JSON, `__pycache__` 제외

### Step 2 — Telegram Bot 핸들러 (`bot/telegram_handler.py`)
- `/start` 커맨드 응답
- 텍스트 메시지(주제) 수신
- 사진 수신 — 앨범(media group) 묶음 처리 (1.5초 버퍼)
- 파이프라인 진행 상태를 실시간으로 메시지 수정하며 표시
- `ALLOWED_TELEGRAM_USER_ID`로 접근 제한

### Step 3 — AI 콘텐츠 생성 (`ai/content_generator.py`)
- 모델: `claude-sonnet-4-6`
- 입력: 주제 텍스트 + 이미지(base64)
- 출력 JSON 구조:
  ```json
  {
    "title": "블로그 제목",
    "slug": "url-friendly-slug",
    "content": "<HTML 본문>",
    "meta_description": "검색 결과 설명",
    "focus_keyword": "대표 키워드",
    "categories": ["카테고리"],
    "tags": ["태그1", "태그2", ...]
  }
  ```
- 시스템 프롬프트에 `cache_control: ephemeral` 적용 (프롬프트 캐싱으로 비용 절감)

### Step 4 — WordPress 게시 (`wordpress/publisher.py`)
- WordPress REST API (`/wp-json/wp/v2/`) 사용
- 이미지 → 미디어 업로드 → `featured_media` ID 획득
- 카테고리·태그 자동 생성 (없으면 새로 만들기)
- Yoast SEO 메타 필드 설정:
  - `_yoast_wpseo_title`
  - `_yoast_wpseo_metadesc`
  - `_yoast_wpseo_focuskw`
- 상태 `publish`로 즉시 공개 → 게시된 URL 반환

### Step 5 — 검색엔진 등록 (`seo/`)
| 엔진 | 방식 | 파일 |
|------|------|------|
| Google | Indexing API v3 (서비스 계정 JSON) | `seo/google_index.py` |
| Bing | Webmaster API `SubmitUrl` | `seo/bing_index.py` |
| 네이버 | 서치어드바이저 OpenAPI `crawler/urls` | `seo/naver_index.py` |

### Step 6 — 진입점 (`main.py`)
- `logging` 설정
- `build_application()` 호출 후 `run_polling()` 실행

---

## 필요한 환경변수 (`.env`)

| 키 | 설명 | 필수 |
|----|------|------|
| `TELEGRAM_BOT_TOKEN` | BotFather에서 발급 | ✅ |
| `ALLOWED_TELEGRAM_USER_ID` | 허용할 텔레그램 User ID (0이면 전체 허용) | 권장 |
| `ANTHROPIC_API_KEY` | Anthropic Console | ✅ |
| `WP_URL` | 워드프레스 사이트 URL | ✅ |
| `WP_USERNAME` | 워드프레스 사용자명 | ✅ |
| `WP_APP_PASSWORD` | 워드프레스 애플리케이션 비밀번호 | ✅ |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Google 서비스 계정 JSON 파일 경로 | 선택 |
| `BING_API_KEY` | Bing Webmaster API 키 | 선택 |
| `NAVER_CLIENT_ID` | 네이버 서치어드바이저 Client ID | 선택 |
| `NAVER_CLIENT_SECRET` | 네이버 서치어드바이저 Secret | 선택 |

---

## 실행 방법

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 키 입력

# 3. 봇 실행
python main.py
```

---

## 남은 작업 (v0.2 이후)

- [ ] WordPress 애플리케이션 비밀번호 발급 가이드
- [ ] Google Cloud 서비스 계정 설정 가이드
- [ ] 이미지 자동 alt 텍스트 설정
- [ ] 글 예약 발행 지원
- [ ] 오류 시 재시도 로직
- [ ] 멀티 사이트(워드프레스 여러 개) 지원
