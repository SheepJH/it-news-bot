"""Telegram 어댑터 — CardContent를 PNG 카드 묶음 + 원문 버튼으로 전송."""

from __future__ import annotations

from src.claude_agent import CardContent
from src.rss_fetcher import Article


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class TelegramSender:
    name = "telegram"

    def send(self, content: CardContent, article: Article) -> None:
        # lazy import: Pillow / telegram 의존성을 slack 환경에서는 안 건드림
        from src.card_generator import render_cards
        from src.telegram_sender import send_link_button, send_media_group

        images = render_cards(content)
        caption = (
            f"<b>{_esc(content.headline)}</b>\n"
            f"<i>출처: {_esc(article.source)}</i>"
        )
        send_media_group(images, caption=caption)
        send_link_button(article.link)
