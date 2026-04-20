import base64
import json
import re
import anthropic

import config

_client = anthropic.AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

_SYSTEM_PROMPT = """당신은 한국어 블로그 전문 작가입니다.
사용자가 주제와 이미지를 제공하면 SEO에 최적화된 블로그 글을 작성합니다.

반드시 아래 JSON 형식으로만 응답하세요. 마크다운 코드블록 없이 순수 JSON만 출력하세요.
JSON 외의 다른 텍스트는 절대 포함하지 마세요:
{
  "title": "블로그 제목 (50자 이내, 핵심 키워드 포함)",
  "slug": "url-friendly-slug-in-english",
  "content": "HTML 본문 (h2, h3, p, ul, ol 태그 사용, 최소 800자)",
  "meta_description": "검색 결과에 표시될 설명 (150자 이내)",
  "focus_keyword": "대표 키워드 1개",
  "categories": ["카테고리1"],
  "tags": ["태그1", "태그2", "태그3", "태그4", "태그5"]
}"""


async def generate_content(topic: str, images_bytes: list[bytes]) -> dict:
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
        "text": f"다음 주제로 블로그 글을 작성해주세요:\n\n{topic}",
    })

    response = await _client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": content_parts}],
    )

    raw = response.content[0].text.strip()

    # 마크다운 코드블록 제거
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # JSON 객체 추출
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    # 제어문자 제거 (탭/줄바꿈 제외)
    raw = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", raw)

    return json.loads(raw)
