# 오늘의 IT 뉴스 봇

매일 아침 8시 Telegram으로 오늘의 IT 뉴스 1개를 카드뉴스로 받아보는 봇.

- 소스: 전자신문 · AI타임스 · GeekNews (RSS)
- 선정: Claude Sonnet 4.6이 오늘의 Top 1 기사 선정
- 카드: 표지 / 핵심 요약 / 인사이트 3장
- 추가: 전문 용어 설명 + 원문 링크 버튼
- 실행: GitHub Actions (KST 08:00)

## 로컬에서 테스트

```bash
pip install -r requirements.txt

# 폰트 다운로드 (1회)
mkdir -p assets
BASE="https://github.com/orioncactus/pretendard/raw/main/packages/pretendard/dist/public/static"
curl -sSL -o assets/Pretendard-Regular.ttf  "$BASE/Pretendard-Regular.ttf"
curl -sSL -o assets/Pretendard-SemiBold.ttf "$BASE/Pretendard-SemiBold.ttf"
curl -sSL -o assets/Pretendard-Bold.ttf    "$BASE/Pretendard-Bold.ttf"

cp .env.example .env
# .env 에 API 키 3개 입력

python main.py
```

## GitHub 배포

1. GitHub에 private 레포 생성 후 push
2. **Settings → Secrets and variables → Actions → New repository secret** 에서 3개 등록:
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. **Actions** 탭 → `Daily IT News` → `Run workflow` 로 수동 테스트
4. 이후 매일 KST 08:00 자동 실행

## 파일 구조

```
it-news-bot/
├── main.py                       # 파이프라인 오케스트레이터
├── src/
│   ├── rss_fetcher.py            # 3개 RSS 수집·필터·중복제거
│   ├── claude_agent.py           # Top 1 선정 + 카드 내용 생성
│   ├── article_scraper.py        # 본문 추출 (newspaper3k)
│   ├── card_generator.py         # Pillow 카드 이미지 3장
│   └── telegram_sender.py        # sendMediaGroup + sendMessage
├── assets/                       # 폰트 (git ignore)
├── output/                       # 생성된 PNG (git ignore)
├── requirements.txt
├── sent_urls.txt                 # 보낸 기사 URL 기록
└── .github/workflows/daily.yml   # cron 스케줄
```
