"""RSS 피드에서 최신 IT 뉴스 기사를 수집한다."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import feedparser

RSS_FEEDS: dict[str, str] = {
    "전자신문": "https://rss.etnews.com/Section901.xml",
    "AI타임스": "https://www.aitimes.com/rss/allArticle.xml",
    "GeekNews": "https://feeds.feedburner.com/geeknews-feed",
}

PER_FEED_LIMIT = 10
HOURS_WINDOW = 24
DEDUPE_THRESHOLD = 0.7


@dataclass
class Article:
    source: str
    title: str
    link: str
    published: datetime
    summary: str

    def to_prompt_line(self, index: int) -> str:
        return f"{index}. [{self.source}] {self.title}"


def _parse_published(entry) -> datetime | None:
    """피드 엔트리에서 발행 시각을 UTC datetime으로 반환."""
    for key in ("published_parsed", "updated_parsed"):
        tm = getattr(entry, key, None)
        if tm:
            return datetime(*tm[:6], tzinfo=timezone.utc)
    return None


def _fetch_feed(source: str, url: str) -> list[Article]:
    parsed = feedparser.parse(url, request_headers={"User-Agent": "Mozilla/5.0"})
    if parsed.bozo and not parsed.entries:
        print(f"[warn] RSS 파싱 실패: {source} ({parsed.bozo_exception})")
        return []

    articles: list[Article] = []
    for entry in parsed.entries[:PER_FEED_LIMIT]:
        published = _parse_published(entry)
        if published is None:
            continue
        articles.append(
            Article(
                source=source,
                title=entry.title.strip(),
                link=entry.link,
                published=published,
                summary=entry.get("summary", "").strip(),
            )
        )
    return articles


def _filter_recent(articles: list[Article], hours: int) -> list[Article]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return [a for a in articles if a.published >= cutoff]


def _dedupe_by_title(articles: list[Article]) -> list[Article]:
    unique: list[Article] = []
    for article in articles:
        if any(
            SequenceMatcher(None, article.title, u.title).ratio() >= DEDUPE_THRESHOLD
            for u in unique
        ):
            continue
        unique.append(article)
    return unique


def collect_candidates() -> list[Article]:
    """3개 RSS에서 기사 수집 → 최근 24시간 필터 → 중복 제거."""
    all_articles: list[Article] = []
    for source, url in RSS_FEEDS.items():
        all_articles.extend(_fetch_feed(source, url))

    recent = _filter_recent(all_articles, HOURS_WINDOW)
    # 주말·새벽 등 24h 내 기사가 너무 적으면 48h로 확장
    if len(recent) < 5:
        recent = _filter_recent(all_articles, HOURS_WINDOW * 2)

    deduped = _dedupe_by_title(recent)
    deduped.sort(key=lambda a: a.published, reverse=True)
    return deduped


if __name__ == "__main__":
    candidates = collect_candidates()
    print(f"후보 기사 {len(candidates)}개\n")
    for i, a in enumerate(candidates):
        print(a.to_prompt_line(i))
