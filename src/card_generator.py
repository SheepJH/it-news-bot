"""카드 이미지를 Pillow로 생성한다.

디자인 언어: **라이트 에디토리얼 프레스** + **카드별 메타포**
- 표지: 포스터 (거대 헤드라인)
- 요약 3장: 팩트 카드 — 이모지 히어로 + 제목 + 본문 (본문 **...** 형광펜)
- 파급효과: 세로 타임라인 — 왼쪽 번호 + 세로 연결선 + 오른쪽 본문
- 스스로에게: 큰 따옴표 안에 담긴 질문 한 줄

공통: 웜 오프화이트 배경 / 딥 버밀리언 악센트 / 상단 헤어라인 매스트헤드
     본문 속 **구절**은 노란 형광펜으로 강조
"""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

from .claude_agent import CardContent, Keyword, SummaryPoint

ASSETS_DIR = Path(__file__).parent.parent / "assets"
ICON_CACHE_DIR = ASSETS_DIR / "icons"

# 정사각형
W, H = 1080, 1080

# 색상 — 라이트 에디토리얼
BG = (245, 242, 234)       # 웜 오프화이트
INK = (26, 24, 22)         # 근접 블랙
ACCENT = (200, 65, 40)     # 딥 버밀리언
MUTED = (125, 120, 112)
HAIRLINE = (205, 200, 188)
PANEL = (235, 230, 220)    # 살짝 어두운 서브 배경
HIGHLIGHT = (255, 228, 115)  # 형광펜 노랑

# 폰트
FONT_BOLD = ASSETS_DIR / "Pretendard-Bold.ttf"
FONT_SEMI = ASSETS_DIR / "Pretendard-SemiBold.ttf"
FONT_REG = ASSETS_DIR / "Pretendard-Regular.ttf"

# 레이아웃
PAD = 80
MAST_TOP = 60
MAST_BOTTOM = 140
MAST_TEXT_Y = MAST_TOP + 28
CONTENT_TOP = MAST_BOTTOM + 60   # 200
CONTENT_MAX_W = W - 2 * PAD
# 하단 용어 영역을 아래로 내려서 2개 항목이 완전히 보이게 (푸터 제거 덕분)
GLOSSARY_TOP = 890
BOTTOM_SAFE = H - PAD            # 실제 하단 가용 한계 (1000)

TWEMOJI_BASE = "https://cdn.jsdelivr.net/gh/twitter/twemoji@latest/assets/72x72"


# ---------------------------------------------------------------------------
# 유틸
# ---------------------------------------------------------------------------


def _load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    if not path.exists():
        return ImageFont.load_default()
    return ImageFont.truetype(str(path), size=size)


def _text_w(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> int:
    b = draw.textbbox((0, 0), text, font=font)
    return b[2] - b[0]


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    """어절(공백) 단위 줄바꿈. 어절 하나가 폭을 넘으면 문자 단위 폴백."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            lines.append("")
            continue
        words = paragraph.split(" ")
        current = ""
        for word in words:
            trial = f"{current} {word}" if current else word
            if _text_w(draw, trial, font) <= max_width:
                current = trial
                continue
            if current:
                lines.append(current)
                current = ""
            if _text_w(draw, word, font) > max_width:
                buf = ""
                for ch in word:
                    t = buf + ch
                    if _text_w(draw, t, font) <= max_width:
                        buf = t
                    else:
                        if buf:
                            lines.append(buf)
                        buf = ch
                current = buf
            else:
                current = word
        if current:
            lines.append(current)
    return lines


def _draw_multiline(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    line_height: int,
    fill=INK,
) -> int:
    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


# ---------------------------------------------------------------------------
# 형광펜 시스템 — **...** 마커 파싱 & 렌더
# ---------------------------------------------------------------------------


def _parse_highlights(text: str) -> tuple[str, list[tuple[int, int]]]:
    """'**...**' 마커를 분리해서 clean_text와 (start,end) 구간들을 반환."""
    out: list[str] = []
    ranges: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    pos = 0
    while i < n:
        if text[i : i + 2] == "**":
            j = text.find("**", i + 2)
            if j == -1:
                out.append(text[i])
                pos += 1
                i += 1
                continue
            inner = text[i + 2 : j]
            start = pos
            out.append(inner)
            pos += len(inner)
            ranges.append((start, pos))
            i = j + 2
        else:
            out.append(text[i])
            pos += 1
            i += 1
    return "".join(out), ranges


def _compute_line_offsets(
    text: str, lines: list[str]
) -> list[tuple[int, int]]:
    """각 wrap된 라인이 clean_text 상에서 차지하는 (start, end) 범위를 계산."""
    offsets: list[tuple[int, int]] = []
    cursor = 0
    n = len(text)
    for line in lines:
        # 라인 간 공백/개행 스킵
        while cursor < n and text[cursor] in (" ", "\n"):
            cursor += 1
        start = cursor
        cursor = min(n, start + len(line))
        offsets.append((start, cursor))
    return offsets


def _glyph_offsets(
    draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont
) -> tuple[int, int]:
    """draw.text((x,0))으로 그렸을 때 글리프 시각 영역의 (top, bottom) y-offset.

    한글 + 영문 혼합 기준점("가A0").
    형광펜 박스를 글자에 정확히 맞추는 데 사용.
    """
    bbox = draw.textbbox((0, 0), "가A0", font=font)
    return bbox[1], bbox[3]


def _draw_multiline_rich(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    line_offsets: list[tuple[int, int]],
    highlights: list[tuple[int, int]],
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    line_height: int,
    fill=INK,
    hl_color=HIGHLIGHT,
) -> int:
    """줄바꿈 후 **...** 구간에 노란 배경을 깔고 그 위에 글자를 렌더."""
    top_off, bot_off = _glyph_offsets(draw, font)
    hl_pad = 3
    for line, (ls, le) in zip(lines, line_offsets):
        # 1) 형광펜 배경 — 글자 글리프 영역에 정확히 맞춤
        for hs, he in highlights:
            s = max(ls, hs)
            e = min(le, he)
            if s >= e:
                continue
            rel_s = s - ls
            rel_e = e - ls
            pre_w = _text_w(draw, line[:rel_s], font)
            seg_w = _text_w(draw, line[rel_s:rel_e], font)
            rect_x1 = x + pre_w - 2
            rect_x2 = rect_x1 + seg_w + 6
            rect_y1 = y + top_off - hl_pad
            rect_y2 = y + bot_off + hl_pad
            draw.rectangle(
                [(rect_x1, rect_y1), (rect_x2, rect_y2)], fill=hl_color
            )
        # 2) 글자
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _draw_rich(
    draw: ImageDraw.ImageDraw,
    raw_text: str,
    font: ImageFont.FreeTypeFont,
    x: int,
    y: int,
    max_width: int,
    line_height: int,
    fill=INK,
) -> int:
    """**...** 마커를 가진 원문을 wrap하고 형광펜과 함께 렌더."""
    clean, highlights = _parse_highlights(raw_text)
    lines = _wrap_text(draw, clean, font, max_width)
    offsets = _compute_line_offsets(clean, lines)
    return _draw_multiline_rich(
        draw, lines, offsets, highlights, font, x, y, line_height, fill=fill
    )


def _hairline(draw: ImageDraw.ImageDraw, y: int, x1: int = PAD, x2: int = W - PAD) -> None:
    draw.rectangle([(x1, y), (x2, y + 1)], fill=HAIRLINE)


def _new_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    return img, ImageDraw.Draw(img)


def _draw_quote_mark(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    size: int = 56,
    color=ACCENT,
) -> None:
    """에디토리얼 이중 따옴표 — 두 개의 기울어진 평행사변형 (여는 따옴표, 상단)."""
    w = max(8, size // 6)
    h = size // 2
    gap = w + 8
    tilt = w
    for i in range(2):
        ox = x + i * (w + gap)
        draw.polygon(
            [
                (ox + tilt, y),
                (ox + tilt + w, y),
                (ox + w, y + h),
                (ox, y + h),
            ],
            fill=color,
        )


def _draw_quote_mark_inverted(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    size: int = 56,
    color=ACCENT,
) -> None:
    """닫는 이중 따옴표 — 상하가 뒤집힌 형태 (하단용)."""
    w = max(8, size // 6)
    h = size // 2
    gap = w + 8
    tilt = w
    for i in range(2):
        ox = x + i * (w + gap)
        draw.polygon(
            [
                (ox, y),
                (ox + w, y),
                (ox + tilt + w, y + h),
                (ox + tilt, y + h),
            ],
            fill=color,
        )


# ---------------------------------------------------------------------------
# Twemoji
# ---------------------------------------------------------------------------


def _emoji_to_codepoint(emoji: str) -> str:
    codes = []
    for ch in emoji:
        code = ord(ch)
        if code == 0xFE0F:
            continue
        codes.append(f"{code:x}")
    return "-".join(codes)


def _load_icon(emoji: str, size: int) -> Optional[Image.Image]:
    if not emoji:
        return None
    ICON_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cp = _emoji_to_codepoint(emoji)
    if not cp:
        return None
    cache = ICON_CACHE_DIR / f"{cp}.png"
    if not cache.exists():
        url = f"{TWEMOJI_BASE}/{cp}.png"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            cache.write_bytes(r.content)
        except Exception as e:
            print(f"[warn] 이모지 '{emoji}' 다운로드 실패 ({url}): {e}")
            return None
    try:
        icon = Image.open(cache).convert("RGBA")
        if icon.size != (size, size):
            icon = icon.resize((size, size), Image.LANCZOS)
        return icon
    except Exception as e:
        print(f"[warn] 이모지 '{emoji}' 로드 실패: {e}")
        return None


def _paste_icon(canvas: Image.Image, emoji: str, x: int, y: int, size: int) -> None:
    icon = _load_icon(emoji, size)
    if icon is None:
        return
    canvas.paste(icon, (x, y), icon)


# ---------------------------------------------------------------------------
# 매스트헤드 / 푸터
# ---------------------------------------------------------------------------


def _draw_masthead(
    draw: ImageDraw.ImageDraw, kicker: str, page: int, total: int
) -> None:
    """신문식 매스트헤드: 헤어라인 — 날짜 · 섹션 · 페이지 — 헤어라인."""
    _hairline(draw, MAST_TOP)
    _hairline(draw, MAST_BOTTOM)

    font = _load_font(FONT_SEMI, 22)
    date_str = datetime.now().strftime("%Y.%m.%d")
    draw.text((PAD, MAST_TEXT_Y), date_str, font=font, fill=INK)

    k = " ".join(kicker.upper())
    kw = _text_w(draw, k, font)
    draw.text(((W - kw) // 2, MAST_TEXT_Y), k, font=font, fill=ACCENT)

    pg = f"{page:02d} / {total:02d}"
    pw = _text_w(draw, pg, font)
    draw.text((W - PAD - pw, MAST_TEXT_Y), pg, font=font, fill=INK)


# ---------------------------------------------------------------------------
# 하단 용어
# ---------------------------------------------------------------------------


def _draw_glossary(draw: ImageDraw.ImageDraw, glossary: list[Keyword]) -> None:
    if not glossary:
        return

    _hairline(draw, GLOSSARY_TOP)

    font_label = _load_font(FONT_SEMI, 17)
    draw.text(
        (PAD, GLOSSARY_TOP + 14),
        " ".join("용어"),
        font=font_label,
        fill=ACCENT,
    )

    font_term = _load_font(FONT_BOLD, 22)
    font_expl = _load_font(FONT_REG, 21)

    y = GLOSSARY_TOP + 44
    for kw in glossary[:2]:
        draw.text((PAD, y), kw.term, font=font_term, fill=INK)
        term_w = _text_w(draw, kw.term, font_term)
        sep = "   ·   "
        draw.text((PAD + term_w, y + 2), sep, font=font_expl, fill=MUTED)
        sep_w = _text_w(draw, sep, font_expl)
        expl_x = PAD + term_w + sep_w
        max_w = W - PAD - expl_x
        lines = _wrap_text(draw, kw.explanation, font_expl, max_w)
        draw.text(
            (expl_x, y + 2),
            lines[0] if lines else "",
            font=font_expl,
            fill=MUTED,
        )
        y += 34


# ---------------------------------------------------------------------------
# 카드 1: 표지 — 포스터
# ---------------------------------------------------------------------------


def _render_cover(content: CardContent, total: int) -> Image.Image:
    img, draw = _new_canvas()
    _draw_masthead(draw, "Today", 1, total)

    # 매거진 악센트 마크
    accent_y = CONTENT_TOP + 10
    draw.rectangle([(PAD, accent_y), (PAD + 72, accent_y + 4)], fill=ACCENT)
    draw.rectangle([(PAD, accent_y + 16), (PAD + 40, accent_y + 20)], fill=ACCENT)

    # 작은 키커
    font_kicker = _load_font(FONT_SEMI, 22)
    draw.text(
        (PAD, accent_y + 48),
        " ".join("HEADLINE"),
        font=font_kicker,
        fill=MUTED,
    )

    # 거대 헤드라인
    font_head = _load_font(FONT_BOLD, 112)
    head_y = accent_y + 100
    lines = _wrap_text(draw, content.headline, font_head, CONTENT_MAX_W)
    _draw_multiline(draw, lines, font_head, PAD, head_y, line_height=130, fill=INK)

    # 하단 서브
    sub_y = BOTTOM_SAFE - 80
    draw.rectangle([(PAD, sub_y), (PAD + 28, sub_y + 2)], fill=INK)
    font_sub = _load_font(FONT_REG, 26)
    draw.text(
        (PAD, sub_y + 18),
        "오늘 가장 중요한 IT 뉴스 한 장",
        font=font_sub,
        fill=MUTED,
    )

    return img


# ---------------------------------------------------------------------------
# 카드 2~4: 요약 — 팩트 카드 (이모지 히어로)
# ---------------------------------------------------------------------------


def _render_summary_point(
    point: SummaryPoint,
    index: int,
    summary_total: int,
    page: int,
    total: int,
) -> Image.Image:
    img, draw = _new_canvas()
    _draw_masthead(draw, "Summary", page, total)

    # ── 상단: 이모지 히어로만 ────────────────────────────
    icon_size = 112
    icon_y = CONTENT_TOP
    _paste_icon(img, point.icon, PAD, icon_y, icon_size)

    # 아래 얇은 풀폭 가로선
    line_y = icon_y + icon_size + 28
    _hairline(draw, line_y)

    # ── 제목 (번호 prefix) ──────────────────────────────
    font_title = _load_font(FONT_BOLD, 56)
    title_y = line_y + 28
    num_text = f"{index}."
    num_w = _text_w(draw, num_text, font_title)
    draw.text((PAD, title_y), num_text, font=font_title, fill=ACCENT)

    title_x = PAD + num_w + 18
    title_max_w = CONTENT_MAX_W - (num_w + 18)
    title_lines = _wrap_text(draw, point.title, font_title, title_max_w)
    title_end = _draw_multiline(
        draw, title_lines, font_title, title_x, title_y, line_height=72, fill=INK
    )

    # 짧은 악센트
    sep_y = title_end + 22
    draw.rectangle([(PAD, sep_y), (PAD + 44, sep_y + 3)], fill=ACCENT)

    # ── 본문 (형광펜 적용) ─────────────────────────────
    font_body = _load_font(FONT_SEMI, 38)
    body_y = sep_y + 28
    _draw_rich(
        draw,
        point.description,
        font_body,
        PAD,
        body_y,
        CONTENT_MAX_W,
        line_height=56,
        fill=INK,
    )

    _draw_glossary(draw, point.glossary)
    return img


# ---------------------------------------------------------------------------
# 카드 5: 파급효과 — 체인 (박스 → 화살표 → 박스)
# ---------------------------------------------------------------------------


def _render_impact(content: CardContent, page: int, total: int) -> Image.Image:
    img, draw = _new_canvas()
    _draw_masthead(draw, "Impact", page, total)

    # 섹션 타이틀
    font_section = _load_font(FONT_BOLD, 50)
    draw.text(
        (PAD, CONTENT_TOP), "파급효과", font=font_section, fill=INK
    )
    underline_y = CONTENT_TOP + 70
    draw.rectangle(
        [(PAD, underline_y), (PAD + 56, underline_y + 3)], fill=ACCENT
    )

    items = content.impact or []
    if not items:
        return img

    # ── 세로 타임라인 영역 ────────────────────────────
    tl_top = underline_y + 56
    tl_bottom = (
        GLOSSARY_TOP - 24 if content.impact_glossary else BOTTOM_SAFE - 20
    )
    available = tl_bottom - tl_top

    n = len(items)
    font_num = _load_font(FONT_BOLD, 30)
    font_body = _load_font(FONT_SEMI, 34)
    line_h = 50

    # 좌측 번호 원 크기 & 컬럼
    circle_d = 52
    col_left_x = PAD + circle_d // 2          # 원의 중심 x
    body_x = PAD + circle_d + 28              # 본문 시작 x
    body_max_w = (W - PAD) - body_x

    # 각 항목 높이 계산 (본문 줄 수 기반)
    slot_heights: list[int] = []
    wrapped_clean: list[tuple[list[str], list[tuple[int, int]], list[tuple[int, int]]]] = []
    for item in items:
        clean, hls = _parse_highlights(item)
        lines = _wrap_text(draw, clean, font_body, body_max_w)
        offsets = _compute_line_offsets(clean, lines)
        wrapped_clean.append((lines, offsets, hls))
        slot_heights.append(max(circle_d + 8, len(lines) * line_h + 14))

    gap = max(24, (available - sum(slot_heights)) // max(1, n))

    y = tl_top
    for i, (slot_h, (lines, offsets, hls)) in enumerate(
        zip(slot_heights, wrapped_clean), start=1
    ):
        # 세로 연결선 (다음 항목까지 — 마지막은 생략)
        if i < n:
            v_top = y + circle_d + 4
            v_bot = y + slot_h + gap - 4
            draw.rectangle(
                [(col_left_x - 1, v_top), (col_left_x + 1, v_bot)],
                fill=HAIRLINE,
            )

        # 번호 원 (악센트 채움)
        cx1 = PAD
        cy1 = y
        cx2 = PAD + circle_d
        cy2 = y + circle_d
        try:
            draw.ellipse([(cx1, cy1), (cx2, cy2)], fill=ACCENT)
        except Exception:
            draw.rectangle([(cx1, cy1), (cx2, cy2)], fill=ACCENT)

        num = f"{i}"
        num_w = _text_w(draw, num, font_num)
        nb = draw.textbbox((0, 0), num, font=font_num)
        num_h = nb[3] - nb[1]
        draw.text(
            (cx1 + (circle_d - num_w) // 2, cy1 + (circle_d - num_h) // 2 - 4),
            num,
            font=font_num,
            fill=BG,
        )

        # 본문 (형광펜 포함)
        body_y = y + 4
        _draw_multiline_rich(
            draw,
            lines,
            offsets,
            hls,
            font_body,
            body_x,
            body_y,
            line_height=line_h,
            fill=INK,
        )

        y += slot_h + gap

    _draw_glossary(draw, content.impact_glossary)
    return img


# ---------------------------------------------------------------------------
# 카드 6: 스스로에게 — 인용 에세이
# ---------------------------------------------------------------------------


def _render_takeaway(
    content: CardContent, page: int, total: int
) -> Image.Image:
    img, draw = _new_canvas()
    _draw_masthead(draw, "For You", page, total)

    # 섹션 타이틀
    font_section = _load_font(FONT_BOLD, 50)
    draw.text(
        (PAD, CONTENT_TOP),
        "오늘 내가 해볼 생각",
        font=font_section,
        fill=INK,
    )
    underline_y = CONTENT_TOP + 70
    draw.rectangle(
        [(PAD, underline_y), (PAD + 56, underline_y + 3)], fill=ACCENT
    )

    question = (content.takeaway or "").strip()
    if not question:
        return img

    # 영역 계산
    area_top = underline_y + 60
    area_bottom = (
        GLOSSARY_TOP - 24 if content.takeaway_glossary else BOTTOM_SAFE - 20
    )
    area_h = area_bottom - area_top

    font_q = _load_font(FONT_BOLD, 50)
    line_h = 72
    hl_pad = 3

    # 따옴표 — 본문 폰트와 같은 패밀리, 사이즈는 살짝 크게
    qmark_size = 64
    font_qmark = _load_font(FONT_BOLD, qmark_size)
    qm_open = "\u201C"   # "
    qm_close = "\u201D"  # "

    qm_o_bbox = draw.textbbox((0, 0), qm_open, font=font_qmark)
    qm_o_w = qm_o_bbox[2] - qm_o_bbox[0]
    qm_c_bbox = draw.textbbox((0, 0), qm_close, font=font_qmark)
    qm_c_w = qm_c_bbox[2] - qm_c_bbox[0]

    side_gap = 10  # 글자와 따옴표 사이 간격
    body_max_w = W - 2 * PAD - 2 * (qm_o_w + side_gap + 4)

    clean, hls = _parse_highlights(question)
    lines = _wrap_text(draw, clean, font_q, body_max_w)
    offsets = _compute_line_offsets(clean, lines)

    top_off, bot_off = _glyph_offsets(draw, font_q)

    total_body_h = len(lines) * line_h
    body_top = area_top + max(0, (area_h - total_body_h) // 2 - 90)

    # ── 본문 (중앙 정렬) + 형광펜 ─────────────────────
    body_y = body_top
    for line, (ls, le) in zip(lines, offsets):
        line_w = _text_w(draw, line, font_q)
        x = (W - line_w) // 2

        for hs, he in hls:
            s = max(ls, hs)
            e = min(le, he)
            if s >= e:
                continue
            rel_s = s - ls
            rel_e = e - ls
            pre_w = _text_w(draw, line[:rel_s], font_q)
            seg_w = _text_w(draw, line[rel_s:rel_e], font_q)
            rect_x1 = x + pre_w - 2
            rect_x2 = rect_x1 + seg_w + 6
            rect_y1 = body_y + top_off - hl_pad
            rect_y2 = body_y + bot_off + hl_pad
            draw.rectangle(
                [(rect_x1, rect_y1), (rect_x2, rect_y2)], fill=HIGHLIGHT
            )

        draw.text((x, body_y), line, font=font_q, fill=INK)
        body_y += line_h

    # ── 따옴표 — 첫 글자 왼쪽 / 마지막 글자 오른쪽 인라인 ──
    # 본문 글자 윗부분에 따옴표 윗부분을 맞춤 (같은 baseline의 cap-line)
    first_line_w = _text_w(draw, lines[0], font_q)
    first_line_x = (W - first_line_w) // 2
    # x: textbbox의 left offset 보정 (음수일 수 있음)
    qm_o_x = first_line_x - side_gap - qm_o_w - qm_o_bbox[0]
    qm_o_y = body_top + top_off - qm_o_bbox[1]
    draw.text((qm_o_x, qm_o_y), qm_open, font=font_qmark, fill=ACCENT)

    last_line_w = _text_w(draw, lines[-1], font_q)
    last_line_x = (W - last_line_w) // 2
    last_line_y = body_top + (len(lines) - 1) * line_h
    qm_c_x = last_line_x + last_line_w + side_gap - qm_c_bbox[0]
    qm_c_y = last_line_y + top_off - qm_c_bbox[1]
    draw.text((qm_c_x, qm_c_y), qm_close, font=font_qmark, fill=ACCENT)

    _draw_glossary(draw, content.takeaway_glossary)
    return img


# ---------------------------------------------------------------------------
# 공개 API
# ---------------------------------------------------------------------------


def _to_buffer(img: Image.Image, name: str) -> BytesIO:
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    buf.name = name
    return buf


def render_cards(content: CardContent) -> list[BytesIO]:
    """표지 + 요약 3 + 영향 + 나에게. 총 6장."""
    summary_n = len(content.summary_points)
    total = 1 + summary_n + 2

    buffers: list[BytesIO] = []
    page = 1

    buffers.append(_to_buffer(_render_cover(content, total), f"{page:02d}_cover.png"))
    page += 1

    for i, point in enumerate(content.summary_points, start=1):
        buffers.append(
            _to_buffer(
                _render_summary_point(point, i, summary_n, page, total),
                f"{page:02d}_summary_{i}.png",
            )
        )
        page += 1

    buffers.append(
        _to_buffer(_render_impact(content, page, total), f"{page:02d}_impact.png")
    )
    page += 1

    buffers.append(
        _to_buffer(_render_takeaway(content, page, total), f"{page:02d}_takeaway.png")
    )

    return buffers


if __name__ == "__main__":
    pass
