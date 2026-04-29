"""Sender Protocol — 채널별 어댑터의 공통 인터페이스."""

from __future__ import annotations

from typing import Protocol

from src.claude_agent import CardContent
from src.rss_fetcher import Article


class Sender(Protocol):
    name: str  # "telegram" | "slack"

    def send(self, content: CardContent, article: Article) -> None: ...
