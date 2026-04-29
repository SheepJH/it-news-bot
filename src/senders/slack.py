"""Slack 어댑터 — PIL 카드 이미지 6장 + 캡션을 채널에 업로드."""

from __future__ import annotations

import os

from src.claude_agent import CardContent
from src.rss_fetcher import Article


class SlackSender:
    name = "slack"

    def __init__(self) -> None:
        from slack_sdk import WebClient

        self._client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
        self._channel = os.environ["SLACK_CHANNEL_ID"]

    def send(self, content: CardContent, article: Article) -> None:
        # lazy import: Pillow 의존성을 텔레그램 환경에서는 안 건드림
        from src.card_generator import render_cards

        images = render_cards(content)

        file_uploads = []
        for i, buf in enumerate(images):
            buf.seek(0)
            file_uploads.append(
                {
                    "file": buf.read(),
                    "filename": f"card{i + 1}.png",
                    "title": f"카드 {i + 1}/{len(images)}",
                }
            )

        initial_comment = (
            f"*{content.headline}*\n"
            f"_출처: {article.source}_\n"
            f"<{article.link}|📖 원문 보기>"
        )

        self._client.files_upload_v2(
            channel=self._channel,
            file_uploads=file_uploads,
            initial_comment=initial_comment,
        )
