"""CardContent → Slack Block Kit JSON 변환 (순수 함수)."""

from __future__ import annotations

import re

from src.claude_agent import CardContent, Keyword
from src.rss_fetcher import Article


def md(text: str) -> str:
    """`**foo**` → `*foo*` (Slack mrkdwn bold)."""
    return re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)


def _glossary_context(items: list[Keyword]) -> dict | None:
    if not items:
        return None
    text = "  ".join(f"_{k.term}_: {k.explanation}" for k in items)
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text}],
    }


def build_blocks(content: CardContent, article: Article) -> list[dict]:
    blocks: list[dict] = []

    # header
    blocks.append(
        {
            "type": "header",
            "text": {"type": "plain_text", "text": content.headline, "emoji": True},
        }
    )

    # 출처
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"출처: <{article.link}|{article.source}>",
                }
            ],
        }
    )

    blocks.append({"type": "divider"})

    # summary_points × 3
    for point in content.summary_points:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{point.icon} {point.title}*\n{md(point.description)}",
                },
            }
        )
        ctx = _glossary_context(point.glossary)
        if ctx:
            blocks.append(ctx)

    blocks.append({"type": "divider"})

    # impact
    impact_text = "*🌊 파급효과*\n• " + "\n• ".join(md(i) for i in content.impact)
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": impact_text},
        }
    )
    ctx = _glossary_context(content.impact_glossary)
    if ctx:
        blocks.append(ctx)

    blocks.append({"type": "divider"})

    # takeaway
    blocks.append(
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*💭 생각해볼 질문*\n> {md(content.takeaway)}",
            },
        }
    )
    ctx = _glossary_context(content.takeaway_glossary)
    if ctx:
        blocks.append(ctx)

    # actions: 원문 보기 버튼
    blocks.append(
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "📖 원문 보기",
                        "emoji": True,
                    },
                    "url": article.link,
                    "style": "primary",
                }
            ],
        }
    )

    return blocks
