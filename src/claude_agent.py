"""Claude Sonnet 4.6으로 Top 1 선정 및 카드 내용 생성."""

from __future__ import annotations

import os
import re
from typing import List

import anthropic
from pydantic import BaseModel, Field

from .rss_fetcher import Article

MODEL = "claude-sonnet-4-6"

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


# ---------------------------------------------------------------------------
# 1단계: Top 1 선정
# ---------------------------------------------------------------------------

SELECT_PROMPT = """\
다음은 오늘의 IT 뉴스 후보입니다. 이 중 가장 중요한 1개를 골라주세요.

선정 기준:
1. 업계 파급력 — 많은 기업/사용자에게 영향을 주는가
2. 독자 관심도 — 일반 독자가 궁금해할 만한 내용인가
3. 장기적 중요성 — 일주일 뒤에도 의미가 있을 사건인가

후보:
{candidates}

답변은 번호만 숫자로 (예: 3). 다른 말 없이 숫자만 출력해주세요.
"""


def pick_top_article(candidates: List[Article]) -> Article:
    """Claude에게 후보 중 1개를 고르게 한다."""
    if not candidates:
        raise ValueError("후보 기사가 없습니다.")

    prompt = SELECT_PROMPT.format(
        candidates="\n".join(a.to_prompt_line(i) for i, a in enumerate(candidates))
    )

    response = _get_client().messages.create(
        model=MODEL,
        max_tokens=20,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text.strip()
    match = re.search(r"\d+", text)
    if not match:
        print(f"[warn] Claude 응답에서 번호를 찾지 못함: {text!r}. 0번으로 폴백.")
        return candidates[0]
    idx = int(match.group()) % len(candidates)
    return candidates[idx]


# ---------------------------------------------------------------------------
# 2단계: 카드 내용 생성 (구조화 출력)
# ---------------------------------------------------------------------------


class Keyword(BaseModel):
    term: str = Field(description="카드 안에서 실제로 쓰인 전문 용어 중 일반인이 모를 만한 것")
    explanation: str = Field(description="매우 짧은 한 줄 설명 (공백 포함 25~45자)")


class SummaryPoint(BaseModel):
    icon: str = Field(description="포인트 내용에 어울리는 이모지 1개 (예: 💰 🤖 📊 🏦 🌐 ⚡ 🔒 📈 🚀 🎯)")
    title: str = Field(description="포인트 한 줄 헤드라인. 공백 포함 18~24자.")
    description: str = Field(
        description=(
            "포인트 설명. 2~3문장, 공백 포함 70~110자. "
            "본문 중 가장 핵심이 되는 숫자/고유명사/구절 딱 1개를 **...**로 감싸 형광펜 강조. "
            "반드시 정확히 1개의 **...** 구간을 포함할 것."
        )
    )
    glossary: List[Keyword] = Field(
        description="이 카드의 title/description에 실제 등장한 생소한 용어 0~2개. 당연한 용어는 넣지 말 것. 없으면 빈 배열."
    )


class CardContent(BaseModel):
    headline: str = Field(description="표지용 임팩트 한 줄. 공백 포함 20~28자.")
    summary_points: List[SummaryPoint] = Field(
        description="기사의 핵심 포인트 정확히 3개. 각 포인트가 독립된 카드 1장이 됨. 중요도/논리 순서대로.",
        min_length=3,
        max_length=3,
    )
    impact: List[str] = Field(
        description=(
            "이 기사로 인해 업계·기술·시장·사용자 쪽에서 실제로 벌어질 파급효과 2~3개. "
            "각 항목은 한 문장, 공백 포함 40~70자. "
            "각 항목 안에 가장 핵심이 되는 구절 딱 1개를 **...**로 감싸 형광펜 강조. "
            "각 항목마다 반드시 정확히 1개의 **...** 구간을 포함할 것."
        )
    )
    impact_glossary: List[Keyword] = Field(
        description="파급효과 카드에 실제 등장한 생소한 용어 0~2개. 없으면 빈 배열."
    )
    takeaway: str = Field(
        description=(
            "독자가 스스로에게 던져볼 가장 본질적인 질문 딱 1개. "
            "'나도 실제로 이걸 해볼까'로 이어지는, 행동·선택·사고로 연결되는 질문. "
            "반드시 물음표(?)로 끝나는 열린 질문. 공백 포함 30~60자 한 문장. "
            "기사 고유의 구체 사실·개념이 들어간 질문. 너무 일반적/뻔한 질문 금지. "
            "핵심 구절 1개는 **...**로 감싸 형광펜 강조. 정확히 1개의 **...** 구간 필수."
        )
    )
    takeaway_glossary: List[Keyword] = Field(
        description="이 질문에 실제 등장한 생소한 용어 0~2개. 없으면 빈 배열."
    )


CARD_PROMPT = """\
다음 IT 기사를 카드뉴스용으로 정리해주세요.

[기사 제목]
{title}

[기사 본문]
{body}

요구사항:

1. headline — 표지용 임팩트 한 줄 (공백 포함 20~28자)

2. summary_points — 핵심 포인트 정확히 3개
   - 각 포인트 = 카드 1장. 서로 겹치지 않는 독립된 내용으로.
   - 중요도 또는 논리 흐름 순서 (예: 사건 → 배경 → 구조)
   - icon: 포인트 내용에 어울리는 이모지 1개 (돈→💰, AI→🤖, 차트→📊, 보안→🔒 등)
   - title: 18~24자 한 줄
   - description: 2~3문장, 70~110자. 숫자/고유명사/구체 사실 포함
   - glossary: 이 카드에 실제 쓰인 생소한 용어 0~2개. 없으면 빈 배열.

3. impact — 이 기사로 인해 벌어질 파급효과 (2~3개)
   - 업계/기술/시장/사용자 관점에서 "무슨 일이 뒤따르는가"
   - 각 항목 한 문장, 40~70자
   - 예: "클라우드 AI 시장에서 아마존이 **구글·MS와 동등한 플레이어**로 격상된다."
   - impact_glossary: 이 카드에 쓰인 생소한 용어 0~2개

4. takeaway — 독자가 스스로에게 던져볼 가장 본질적 질문 딱 1개
   - 가장 중요한, "내가 실제로 해볼 생각"으로 이어지는 질문 하나만.
   - 반드시 물음표(?)로 끝나는 열린 질문. 평서문 X, 단정 X, 행동 지시 X.
   - '앞으로 어떻게 될까 / 내가 어떻게 연결할까 / 무엇이 바뀔까' 관점
   - 한 문장, 30~60자. 너무 일반적/뻔한 질문 금지(예: "이게 좋은 일일까?" X)
   - 기사 고유의 구체 사실·개념을 질문 안에 녹여낼 것
   - 예: "AI 투자가 **'상호 약정' 구조**로 굳으면 독립 스타트업의 자리는 어디에 남을까?"
   - takeaway_glossary: 이 카드에 쓰인 생소한 용어 0~2개

공통 — **...** 형광펜 강조 규칙 (매우 중요):
- summary_points 각각의 description, impact 각 항목, takeaway 본문 — 이 세 곳에
  반드시 **각각 정확히 1개씩** "**...**" 마커로 핵심 구절을 감쌀 것.
- 예: "기업가치는 직전 라운드 대비 **약 2배 상승**했다."
- 마커 안은 너무 길지 않게 (공백 포함 4~14자 정도), 해당 문장에서 가장
  눈에 박히는 숫자/고유명사/결정적 구절을 고를 것.
- title, headline에는 **...** 마커를 쓰지 말 것.

공통 — glossary 규칙:
- 각 카드에 실제 등장한 용어만 (기사 본문에만 있고 카드에 없는 건 X)
- 일반인이 모를 만한 것만. 당연한 단어(AI, 투자, 시장 등)는 제외.
- explanation은 한 줄, 25~45자. "~는 ~이다" 형태로 간결하게.

본문이 영어이면 모두 한국어로 작성해주세요.
"""


def generate_card_content(title: str, body: str) -> CardContent:
    """기사 본문으로부터 카드 내용을 생성."""
    prompt = CARD_PROMPT.format(
        title=title,
        body=body or "(본문을 가져오지 못했습니다. 제목 기반으로 작성해주세요.)",
    )

    response = _get_client().messages.parse(
        model=MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
        output_format=CardContent,
    )
    return response.parsed_output
