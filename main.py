"""오늘의 IT 뉴스 카드를 생성해 설정된 채널(Telegram/Slack)로 전송한다.

실행: python main.py
"""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv

from src.article_scraper import fetch_body
from src.claude_agent import generate_card_content, pick_top_article
from src.rss_fetcher import collect_candidates
from src.senders import get_sender

SENT_LOG = Path(__file__).parent / "sent_urls.txt"


def _load_sent_urls() -> set[str]:
    if not SENT_LOG.exists():
        return set()
    return {line.strip() for line in SENT_LOG.read_text().splitlines() if line.strip()}


def _append_sent_url(url: str) -> None:
    with SENT_LOG.open("a") as f:
        f.write(url + "\n")


def main() -> None:
    load_dotenv()
    sender = get_sender()  # fail-fast: 토큰 누락 시 Claude 호출 전에 즉시 실패
    print(f"채널: {sender.name}")

    print("1/5 RSS 수집 중…")
    candidates = collect_candidates()
    if not candidates:
        print("후보 기사가 없습니다. 종료.")
        return

    sent = _load_sent_urls()
    candidates = [c for c in candidates if c.link not in sent]
    if not candidates:
        print("새로 보낼 기사가 없습니다. 종료.")
        return
    print(f"   후보 {len(candidates)}개")

    print("2/5 Claude가 Top 1 선정 중…")
    top = pick_top_article(candidates)
    print(f"   선정: [{top.source}] {top.title}")

    print("3/5 본문 추출 중…")
    body = fetch_body(top.link)
    if not body:
        # 본문 없으면 RSS summary로 폴백
        body = top.summary
    print(f"   본문 길이: {len(body)}자")

    print("4/5 카드 내용 생성 중…")
    content = generate_card_content(top.title, body)
    print(f"   헤드라인: {content.headline}")

    print("5/5 카드 전송 중…")
    sender.send(content, top)

    _append_sent_url(top.link)
    print("완료!")


if __name__ == "__main__":
    main()
