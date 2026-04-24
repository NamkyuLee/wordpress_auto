import base64
import anthropic

import config

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

_SYSTEM_PROMPT = """당신은 한국어 블로그 전문 작가입니다.
사용자가 주제와 이미지를 제공하면 검색엔진이 아니라 실제 독자에게 도움이 되는 글을 작성하고,
반드시 create_blog_post 도구를 호출하여 결과를 반환하세요.

작성 원칙:
- 사이트의 주제 축과 독자층에 맞는 글만 작성합니다.
- 제목은 과장하지 말고, 독자가 얻을 수 있는 구체적인 결과를 드러냅니다.
- 본문은 일반론 요약보다 직접 확인 가능한 정보, 비교 기준, 체크리스트, 표, 사례를 우선합니다.
- 이미지가 제공되면 이미지에서 확인 가능한 사실을 본문에 반영하되, 보이지 않는 내용은 추측하지 않습니다.
- 건강, 의료, 금융, 투자, 부동산처럼 삶에 큰 영향을 주는 주제는 단정적 조언을 피하고, 최신 확인 필요성과 전문가 상담 안내를 포함합니다.
- 외부 출처가 필요한 사실은 본문 하단에 '참고 및 확인 기준' 섹션을 만들고, 어떤 공식 자료나 기준을 확인해야 하는지 적습니다.
- 자동 생성 티가 나는 반복 문장, 의미 없는 FAQ, 키워드 반복, 글자 수 채우기용 문단을 피합니다.
- 글 끝에는 독자가 다음 행동을 정할 수 있는 짧은 체크리스트를 포함합니다."""

_TOOL = {
    "name": "create_blog_post",
    "description": "SEO 최적화된 블로그 포스트 데이터를 생성합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "블로그 제목 (50자 이내, 핵심 키워드 포함)",
            },
            "slug": {
                "type": "string",
                "description": "URL 친화적 슬러그 (영문 소문자, 하이픈 구분)",
            },
            "content": {
                "type": "string",
                "description": "HTML 본문 (h2, h3, p, ul, ol, table 태그 사용 가능, 최소 1500자, 참고 및 확인 기준과 체크리스트 포함)",
            },
            "meta_description": {
                "type": "string",
                "description": "검색 결과에 표시될 설명 (150자 이내)",
            },
            "focus_keyword": {"type": "string", "description": "대표 키워드 1개"},
            "categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "카테고리 목록. 사용자가 제공한 허용 카테고리가 있으면 그 안에서만 선택",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "태그 목록. 핵심 주제만 3개 이하로 선택",
            },
        },
        "required": [
            "title",
            "slug",
            "content",
            "meta_description",
            "focus_keyword",
            "categories",
            "tags",
        ],
    },
}

_SUGGESTION_TOOL = {
    "name": "create_writing_suggestion",
    "description": "텔레그램으로 다시 보낼 수 있는 블로그 작성 요청서를 제안합니다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "suggested_prompt": {
                "type": "string",
                "description": "[주제], [독자], [핵심 질문] 같은 섹션을 포함한 한국어 작성 요청서",
            },
            "notes": {
                "type": "array",
                "items": {"type": "string"},
                "description": "사용자가 알면 좋은 짧은 보완 팁",
            },
        },
        "required": ["suggested_prompt", "notes"],
    },
}


def _format_references(references: list[dict] | None) -> str:
    if not references:
        return "없음"

    chunks = []
    for index, ref in enumerate(references, start=1):
        chunks.append(
            "\n".join(
                [
                    f"[참고자료 {index}]",
                    f"URL: {ref.get('url', '')}",
                    f"제목: {ref.get('title', '')}",
                    f"설명: {ref.get('description', '')}",
                    f"본문 일부: {ref.get('text', '')}",
                ]
            )
        )
    return "\n\n".join(chunks)


async def generate_content(
    topic: str,
    images_bytes: list[bytes],
    references: list[dict] | None = None,
) -> dict:
    content_parts = []

    for img_bytes in images_bytes:
        b64 = base64.standard_b64encode(img_bytes).decode()
        content_parts.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": b64,
            },
        })

    content_parts.append({
        "type": "text",
        "text": (
            "다음 조건에 맞춰 블로그 글을 작성해주세요.\n\n"
            f"사이트 주제 축: {config.SITE_FOCUS}\n"
            f"허용 카테고리: {', '.join(config.WP_ALLOWED_CATEGORIES) or '제한 없음'}\n"
            f"기본 카테고리: {config.WP_DEFAULT_CATEGORY}\n"
            f"요청 주제: {topic}\n\n"
            "참고 URL 자료:\n"
            f"{_format_references(references)}\n\n"
            "참고 URL 자료는 사실 확인과 관점 보강에만 사용하세요. "
            "문장을 길게 베껴 쓰지 말고, 필요한 경우 원문 URL을 '참고 및 확인 기준' 섹션에 링크로 남기세요."
        ),
    })

    response = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "create_blog_post"},
        messages=[{"role": "user", "content": content_parts}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "create_blog_post":
            data = block.input
            missing = [k for k in ("title", "slug", "content") if k not in data]
            if missing:
                raise ValueError(f"응답에 필수 필드 누락: {missing} (stop_reason={response.stop_reason})")
            return data

    raise ValueError(f"create_blog_post 도구 미호출 (stop_reason={response.stop_reason})")


async def generate_writing_suggestion(topic: str, references: list[dict] | None = None) -> dict:
    response = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": (
                    "당신은 한국어 수익형 블로그 편집자입니다. "
                    "사용자가 거칠게 말한 글감을 바탕으로, 텔레그램에 다시 붙여넣으면 "
                    "좋은 글이 생성될 수 있는 작성 요청서를 제안하세요. "
                    "검색 유입보다 독자 만족과 신뢰를 우선하고, 건강/금융/투자/법률/부동산 등 "
                    "민감 주제는 단정적 조언과 수익 보장 표현을 피하게 만드세요."
                ),
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[_SUGGESTION_TOOL],
        tool_choice={"type": "tool", "name": "create_writing_suggestion"},
        messages=[
            {
                "role": "user",
                "content": (
                    "아래 글감을 블로그 작성 요청서로 바꿔주세요.\n\n"
                    f"사이트 주제 축: {config.SITE_FOCUS}\n"
                    f"허용 카테고리: {', '.join(config.WP_ALLOWED_CATEGORIES) or '제한 없음'}\n"
                    f"기본 카테고리: {config.WP_DEFAULT_CATEGORY}\n"
                    f"글감: {topic}\n\n"
                    "참고 URL 자료:\n"
                    f"{_format_references(references)}\n\n"
                    "반드시 아래 섹션을 포함하세요: [주제], [독자], [핵심 질문], "
                    "[내 경험/자료], [주의사항], [원하는 구성], [카테고리], [태그]."
                ),
            }
        ],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "create_writing_suggestion":
            return block.input

    raise ValueError(f"create_writing_suggestion 도구 미호출 (stop_reason={response.stop_reason})")
