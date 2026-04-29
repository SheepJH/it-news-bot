"""카드 템플릿 미리보기.

실제 RSS/Claude API 없이 더미 데이터로 6장 카드를 렌더링해서
output/preview/ 폴더에 고정 파일명으로 저장한다.

사용:
    python3 preview_cards.py
"""

from __future__ import annotations

from pathlib import Path

from src.card_generator import (
    _render_cover,
    _render_impact,
    _render_summary_point,
    _render_takeaway,
)
from src.claude_agent import CardContent, Keyword, SummaryPoint

PREVIEW_DIR = Path(__file__).parent / "output" / "preview"


SAMPLE = CardContent(
    headline="앤트로픽, 아마존 50억달러 딜",
    summary_points=[
        SummaryPoint(
            icon="💰",
            title="앤트로픽, 아마존에서 50억$ 유치",
            description="앤트로픽은 아마존으로부터 역대 최대 규모인 **50억 달러** 투자를 받는다. 기업가치는 직전 라운드 대비 약 2배 상승했다.",
            glossary=[
                Keyword(term="앤트로픽", explanation="Claude 모델을 만드는 AI 스타트업"),
            ],
        ),
        SummaryPoint(
            icon="🤝",
            title="대가로 AWS에 1000억$ 약정",
            description="앤트로픽은 향후 AWS 인프라에 **1000억 달러**를 쓰기로 약속했다. 이는 '투자-사용' 상호 구조의 최대 규모 사례다.",
            glossary=[
                Keyword(term="AWS", explanation="아마존의 클라우드 컴퓨팅 서비스"),
            ],
        ),
        SummaryPoint(
            icon="🏦",
            title="MS-OpenAI 딜과 닮은 구조",
            description="마이크로소프트-OpenAI의 Azure 약정과 유사한 패턴이다. 빅테크가 AI 모델사를 **클라우드 고정 고객**으로 락인하는 흐름이 굳어지고 있다.",
            glossary=[
                Keyword(term="Azure", explanation="마이크로소프트의 클라우드 서비스"),
                Keyword(term="락인", explanation="고객이 특정 서비스에 묶이는 현상"),
            ],
        ),
    ],
    impact=[
        "AWS가 MS Azure에 이어 **AI 인프라 경쟁의 유력 축**으로 복귀한다.",
        "AI 모델사들의 **'클라우드 락인' 구조**가 업계 표준으로 굳는다.",
        "중소 AI 스타트업은 **독립적 인프라 선택지**가 더 좁아진다.",
    ],
    impact_glossary=[
        Keyword(term="AI 인프라", explanation="모델 학습·추론용 GPU·데이터센터"),
    ],
    takeaway="AI 투자가 **'상호 약정' 구조**로 굳으면 독립 스타트업의 자리는 어디에 남을까?",
    takeaway_glossary=[
        Keyword(term="상호 약정", explanation="투자와 사용처를 맞바꾸는 자본 구조"),
    ],
)


def main() -> None:
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)

    total = 1 + len(SAMPLE.summary_points) + 2  # 표지 + 요약 + 파급효과 + 생각해볼 점

    outputs: list[tuple[str, "Image"]] = []  # type: ignore[name-defined]

    # 표지
    outputs.append(("01_cover.png", _render_cover(SAMPLE, total)))

    # 요약 3장
    page = 2
    for i, point in enumerate(SAMPLE.summary_points, start=1):
        outputs.append(
            (
                f"{page:02d}_summary_{i}.png",
                _render_summary_point(point, i, len(SAMPLE.summary_points), page, total),
            )
        )
        page += 1

    # 파급효과
    outputs.append((f"{page:02d}_impact.png", _render_impact(SAMPLE, page, total)))
    page += 1

    # 생각해볼 점
    outputs.append((f"{page:02d}_takeaway.png", _render_takeaway(SAMPLE, page, total)))

    for name, img in outputs:
        path = PREVIEW_DIR / name
        img.save(path, format="PNG", optimize=True)
        print(f"  {path}")

    print(f"\n총 {len(outputs)}장 → {PREVIEW_DIR}")


if __name__ == "__main__":
    main()
