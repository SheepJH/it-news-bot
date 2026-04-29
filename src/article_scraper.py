"""선정된 기사 URL에서 본문 텍스트를 추출한다."""

from __future__ import annotations

from newspaper import Article as NewsArticle

MAX_CHARS = 8000  # Claude로 넘길 본문 최대 길이


def fetch_body(url: str) -> str:
    """URL에서 본문 텍스트를 추출. 실패 시 빈 문자열."""
    try:
        article = NewsArticle(url, language="ko")
        article.download()
        article.parse()
        text = (article.text or "").strip()
        return text[:MAX_CHARS]
    except Exception as exc:  # 뉴스 사이트 구조가 제각각이라 광범위하게 캐치
        print(f"[warn] 본문 추출 실패: {url} ({exc})")
        return ""


if __name__ == "__main__":
    import sys

    url = sys.argv[1] if len(sys.argv) > 1 else "https://www.etnews.com/"
    body = fetch_body(url)
    print(body[:500])
