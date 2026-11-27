#!/usr/bin/env python3
"""Fetch Korean community hot issues & hot deals, cluster duplicates, classify moods, and enrich with AI summaries."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path
from lxml import etree, html

KST = timezone(timedelta(hours=9))
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

NSFW_KEYWORDS = [
    "ㅇㅎ", "후방", "19금", "약혐", "극혐", "성매매", "성범죄", "성폭행",
    "성인배우", "av배우", "야동", "노출", "몸매", "비키니", "속옷",
]

POLITICS_KEYWORDS = [
    "대통령", "국회", "의원", "정당", "민주당", "국민의힘", "국힘", "조국", "이재명",
    "윤석열", "한동훈", "탄핵", "총선", "대선", "정치", "여당", "야당", "국정",
    "비례", "공천", "징계", "윤리심판", "검찰", "특검", "계엄", "보수", "진보",
    "페미", "한남", "이대남", "혐오", "갈등",
]

SENSITIVE_KEYWORDS = NSFW_KEYWORDS + POLITICS_KEYWORDS + [
    "살인", "사망", "자살", "참사", "폭행", "학대", "마약", "음주운전", "체포", "구속",
]

MOOD_RULES = {
    "politics_conflict": SENSITIVE_KEYWORDS,
    "it_econ": [
        "삼성", "애플", "아이폰", "갤럭시", "맥북", "ai", "챗gpt", "주식", "코인",
        "비트코인", "부동산", "집값", "아파트", "금리", "환율", "경제", "증시",
        "테슬라", "엔비디아", "구글", "마소", "개발", "코딩", "컴퓨터", "그래픽카드",
        "ssd", "모니터", "키보드", "할인", "특가", "쿠팡", "알리", "네이버페이",
    ],
    "sports": [
        "야구", "축구", "농구", "배구", "롤", "lck", "페이커", "손흥민", "이강인",
        "김민재", "류현진", "오타니", "kbo", "epl", "챔스", "올림픽", "게임",
        "스팀", "플스", "닌텐도", "스위치", "복싱", "격투기", "ufc", "골프",
    ],
    "info": [
        "꿀팁", "방법", "정리", "추천", "후기", "리뷰", "주의", "공지", "지원금",
        "청약", "연말정산", "세금", "건강", "병원", "요리", "레시피", "청소", "생활",
        "정보", "요약", "가이드", "예약", "혜택",
    ],
    "life": [
        "기부", "후원", "감동", "결혼", "육아", "아기", "엄마", "아빠", "가족",
        "강아지", "고양이", "반려", "냥이", "댕댕이", "출근", "퇴근", "치킨",
        "커피", "여행", "일상", "사연", "선행", "봉사",
    ],
}

STOPWORDS = {
    "ㅋㅋ", "ㅋㅋㅋ", "ㅎㅎ", "ㅎㅎㅎ", "진짜", "레전드", "근황", "논란", "충격",
    "이유", "결말", "실화", "미친", "대박", "속보", "단독", "펌", "오늘", "현재",
    "요즘", "갑자기", "결국", "이거", "저거", "그냥", "무슨", "어떻게", "사람들",
    "한국", "우리", "있는", "없는", "하는", "되는", "같은", "대한", "관련",
}


def fetch_bytes(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def clean_text(text: str | None) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def parse_int(text: str | None) -> int:
    if not text:
        return 0
    m = re.search(r"[\d,]+", text)
    if not m:
        return 0
    return int(m.group(0).replace(",", ""))


def make_post_id(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()[:12]


def fetch_clien_park(limit: int = 25) -> list[dict]:
    url = "https://www.clien.net/service/board/park?od=T33"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    for row in doc.xpath("//div[contains(@class,'list_item') and contains(@class,'symph_row')]"):
        title = clean_text(" ".join(row.xpath(".//span[contains(@class,'subject_fixed')]/text()")))
        href = row.xpath(".//a[contains(@class,'list_subject')]/@href")
        if not title or not href:
            continue
        link = "https://www.clien.net" + href[0].split("?")[0]
        hit = parse_int("".join(row.xpath(".//span[contains(@class,'hit')]/text()")))
        symph = parse_int("".join(row.xpath(".//div[contains(@class,'list_symph')]//span/text()")))
        reply = parse_int("".join(row.xpath(".//span[contains(@class,'rSymph05')]/text()")))
        time_str = clean_text("".join(row.xpath(".//span[contains(@class,'timestamp')]/text()")))
        items.append({
            "id": make_post_id(link),
            "category": "issue",
            "source": "클리앙",
            "source_id": "clien",
            "title": title,
            "url": link,
            "views": hit,
            "likes": symph,
            "comments": reply,
            "time_label": time_str or "오늘",
        })
        if len(items) >= limit:
            break
    return items


def fetch_bobaedream(limit: int = 25) -> list[dict]:
    url = "https://www.bobaedream.co.kr/list?code=best"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    for row in doc.xpath("//tr[@itemtype='http://schema.org/Article']"):
        a = row.xpath(".//a[contains(@class,'bsubject')]")
        if not a:
            continue
        title = clean_text(a[0].text_content())
        href = a[0].get("href", "")
        if not title or not href:
            continue
        link = href if href.startswith("http") else "https://www.bobaedream.co.kr" + href
        reply = parse_int("".join(row.xpath(".//span[contains(@class,'totreply')]/text()")))
        likes = parse_int("".join(row.xpath(".//td[contains(@class,'recomm')]/text()")))
        views = parse_int("".join(row.xpath(".//td[contains(@class,'count')]/text()")))
        date_str = clean_text("".join(row.xpath(".//td[contains(@class,'date')]/text()")))
        items.append({
            "id": make_post_id(link),
            "category": "issue",
            "source": "보배드림",
            "source_id": "bobae",
            "title": title,
            "url": link,
            "views": views,
            "likes": likes,
            "comments": reply,
            "time_label": date_str or "오늘",
        })
        if len(items) >= limit:
            break
    return items


def fetch_slrclub(limit: int = 20) -> list[dict]:
    url = "https://www.slrclub.com/bbs/zboard.php?id=hot_article"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    for row in doc.xpath("//table[@id='bbs_list']//tbody/tr"):
        a = row.xpath(".//td[contains(@class,'sbj')]//a")
        if not a:
            continue
        title = clean_text(a[0].text_content())
        href = a[0].get("href", "")
        if not title or not href:
            continue
        link = href if href.startswith("http") else "https://www.slrclub.com" + href
        sbj_txt = clean_text("".join(row.xpath(".//td[contains(@class,'sbj')]/text()")))
        reply = parse_int(sbj_txt)
        views = parse_int("".join(row.xpath(".//td[contains(@class,'list_click')]/text()")))
        likes = parse_int("".join(row.xpath(".//td[contains(@class,'list_vote')]/text()")))
        date_str = clean_text("".join(row.xpath(".//td[contains(@class,'list_date')]/text()")))
        items.append({
            "id": make_post_id(link),
            "category": "issue",
            "source": "SLR클럽",
            "source_id": "slr",
            "title": title,
            "url": link,
            "views": views,
            "likes": likes,
            "comments": reply,
            "time_label": date_str or "오늘",
        })
        if len(items) >= limit:
            break
    return items


def fetch_humoruniv(limit: int = 20) -> list[dict]:
    url = "https://web.humoruniv.com/board/humor/list.html?table=pds"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    for row in doc.xpath("//tr[starts-with(@id,'li_chk_pds-')]"):
        a = row.xpath(".//td[contains(@class,'li_sbj')]//a")
        if not a:
            continue
        title = clean_text(a[0].text_content())
        href = a[0].get("href", "")
        if not title or not href:
            continue
        title = re.sub(r"\s*\[\d+\]\s*$", "", title)
        link = href if href.startswith("http") else "https://web.humoruniv.com/board/humor/" + href.lstrip("/")
        reply = parse_int("".join(row.xpath(".//span[contains(@class,'list_comment_num')]/text()")))
        views = parse_int("".join(row.xpath(".//td[contains(@class,'li_und')][1]/text()")))
        likes = parse_int("".join(row.xpath(".//td[contains(@class,'li_und')][2]//span/text()")))
        date_str = clean_text("".join(row.xpath(".//td[contains(@class,'li_date')]/text()")))
        items.append({
            "id": make_post_id(link),
            "category": "issue",
            "source": "웃긴대학",
            "source_id": "humoruniv",
            "title": title,
            "url": link,
            "views": views,
            "likes": likes,
            "comments": reply,
            "time_label": date_str or "오늘",
        })
        if len(items) >= limit:
            break
    return items


def fetch_ppomppu_deal_rss(limit: int = 25) -> list[dict]:
    url = "https://www.ppomppu.co.kr/rss.php?id=ppomppu"
    root = etree.fromstring(fetch_bytes(url))
    items = []
    for it in root.xpath("//item")[:limit]:
        title = clean_text(it.findtext("title"))
        link = clean_text(it.findtext("link"))
        pub = clean_text(it.findtext("pubDate"))
        if not title or not link:
            continue
        time_label = "오늘"
        if pub:
            try:
                dt = parsedate_to_datetime(pub).astimezone(KST)
                time_label = dt.strftime("%m-%d %H:%M")
            except Exception:
                pass
        items.append({
            "id": make_post_id(link),
            "category": "deal",
            "source": "뽐뿌",
            "source_id": "ppomppu",
            "title": title,
            "url": link,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "time_label": time_label,
        })
    return items


def fetch_clien_jirum(limit: int = 25) -> list[dict]:
    url = "https://www.clien.net/service/board/jirum"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    for row in doc.xpath("//div[contains(@class,'list_item') and contains(@class,'symph_row')]"):
        a = row.xpath(".//span[contains(@class,'list_subject')]//a")
        if not a:
            a = row.xpath(".//a[contains(@href,'/service/board/jirum/')]")
        if not a:
            continue
        title = clean_text(a[0].text_content())
        href = a[0].get("href", "")
        if not title or not href:
            continue
        link = "https://www.clien.net" + href.split("?")[0]
        hit = parse_int("".join(row.xpath(".//span[contains(@class,'hit')]/text()")))
        symph = parse_int("".join(row.xpath(".//div[contains(@class,'list_symph')]//span/text()")))
        reply = parse_int("".join(row.xpath(".//span[contains(@class,'rSymph05')]/text()")))
        time_str = clean_text("".join(row.xpath(".//span[contains(@class,'timestamp')]/text()")))
        items.append({
            "id": make_post_id(link),
            "category": "deal",
            "source": "클리앙 알뜰",
            "source_id": "clien_deal",
            "title": title,
            "url": link,
            "views": hit,
            "likes": symph,
            "comments": reply,
            "time_label": time_str or "오늘",
        })
        if len(items) >= limit:
            break
    return items


def fetch_damoang_deal(limit: int = 20) -> list[dict]:
    url = "https://damoang.net/economy"
    doc = html.fromstring(fetch_bytes(url).decode("utf-8", "ignore"))
    items = []
    seen = set()
    for a in doc.xpath("//a[contains(@href,'/economy/')]"):
        href = a.get("href", "")
        if not re.search(r"/economy/\d+$", href):
            continue
        if href in seen:
            continue
        txt = clean_text(a.text_content())
        if not txt or txt.startswith("공지") or len(txt) < 6:
            continue
        txt = re.sub(r"^\d+\s*(진행중|종료|품절)\s*", "", txt)
        txt = re.sub(r"\s+N\s+.*$", "", txt)
        if len(txt) < 5:
            continue
        seen.add(href)
        link = href if href.startswith("http") else "https://damoang.net" + href
        items.append({
            "id": make_post_id(link),
            "category": "deal",
            "source": "다모앙 알뜰",
            "source_id": "damoang_deal",
            "title": txt,
            "url": link,
            "views": 0,
            "likes": 0,
            "comments": 0,
            "time_label": "오늘",
        })
        if len(items) >= limit:
            break
    return items


def compute_hot_score(item: dict) -> float:
    base = item.get("likes", 0) * 18 + item.get("comments", 0) * 9 + item.get("views", 0) * 0.06
    if item.get("category") == "deal" and base == 0:
        base = 50.0
    return round(base, 1)


def rule_classify(item: dict) -> tuple[str, bool, bool, bool, bool]:
    title_low = item["title"].lower()
    is_nsfw = any(kw in title_low for kw in NSFW_KEYWORDS)
    is_politics = any(kw in title_low for kw in POLITICS_KEYWORDS)
    is_sensitive = is_nsfw or is_politics or any(kw in title_low for kw in SENSITIVE_KEYWORDS)
    if item.get("category") == "deal":
        return "it_econ", is_sensitive, is_nsfw, is_politics, False

    for mood, kws in MOOD_RULES.items():
        if any(kw in title_low for kw in kws):
            return mood, (is_sensitive or mood == "politics_conflict"), is_nsfw, is_politics, (mood == "sports")
    return "humor", is_sensitive, is_nsfw, is_politics, False


def parse_age_minutes(time_label: str) -> int | None:
    if not time_label:
        return None
    s = time_label.strip()
    m = re.match(r"^(\d+)\s*분\s*전$", s)
    if m:
        return int(m.group(1))
    m = re.match(r"^(\d+)\s*시간\s*전$", s)
    if m:
        return int(m.group(1)) * 60
    m = re.match(r"^(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}(?::\d{2})?)$", s)
    if m:
        fmt = "%Y-%m-%d %H:%M:%S" if len(s) == 19 else "%Y-%m-%d %H:%M"
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=KST)
            diff = (datetime.now(KST) - dt).total_seconds() / 60.0
            return max(0, int(round(diff)))
        except Exception:
            return None
    return None


def extract_tokens(title: str) -> set[str]:
    t = re.sub(r"\.(jpg|jpeg|png|gif|mp4|webp|manhwa|insta)", " ", title, flags=re.I)
    t = re.sub(r"^(펌\)|속보\)|단독\)|ㅇㅎ\??|약혐\)|후방\)|\[[^\]]+\])\s*", "", t)
    t = re.sub(r"답글추천\s*\+\d+", " ", t)
    t = re.sub(r"[^\w가-힣\s]", " ", t).lower()
    words = [w for w in t.split() if len(w) >= 2 and w not in STOPWORDS]
    tokens = set(words)
    # Add 2-char shingles for longer Korean compound words
    for w in words:
        if len(w) >= 4:
            for i in range(len(w) - 1):
                tokens.add(w[i : i + 2])
    return tokens


def is_similar(t1: set[str], t2: set[str]) -> bool:
    if not t1 or not t2:
        return False
    inter = len(t1 & t2)
    union = len(t1 | t2)
    jaccard = inter / union if union else 0.0
    if jaccard >= 0.38:
        return True
    # Also match if at least 3 meaningful tokens overlap and smaller set is small
    min_len = min(len(t1), len(t2))
    if min_len >= 3 and inter >= 3 and (inter / min_len) >= 0.55:
        return True
    return False


def cluster_items(items: list[dict]) -> list[dict]:
    for it in items:
        it["hotScore"] = compute_hot_score(it)
        mood, is_sens, is_nsfw, is_politics, is_sports = rule_classify(it)
        it["mood"] = mood
        it["isSensitive"] = is_sens
        it["isNsfw"] = is_nsfw
        it["isPolitics"] = is_politics
        it["isSports"] = is_sports
        it["ageMinutes"] = parse_age_minutes(it.get("time_label", ""))
        it["_tokens"] = extract_tokens(it["title"])

    # Sort descending by hotScore so strongest item becomes cluster representative
    sorted_items = sorted(items, key=lambda x: x["hotScore"], reverse=True)
    clusters: list[dict] = []

    for it in sorted_items:
        matched_cluster = None
        for cl in clusters:
            if cl["category"] != it["category"]:
                continue
            if is_similar(cl["_tokens"], it["_tokens"]):
                matched_cluster = cl
                break

        if matched_cluster is None:
            clusters.append({
                "clusterId": "cl_" + it["id"],
                "category": it["category"],
                "rep": it,
                "members": [it],
                "_tokens": set(it["_tokens"]),
            })
        else:
            matched_cluster["members"].append(it)
            matched_cluster["_tokens"] |= it["_tokens"]

    result = []
    for cl in clusters:
        rep = dict(cl["rep"])
        rep.pop("_tokens", None)
        members = []
        seen_sources = []
        for m in cl["members"]:
            if m["source"] not in seen_sources:
                seen_sources.append(m["source"])
            m_clean = {k: v for k, v in m.items() if k != "_tokens"}
            members.append(m_clean)

        cross_count = len(seen_sources)
        rep["clusterId"] = cl["clusterId"]
        rep["communities"] = seen_sources
        rep["crossCount"] = cross_count
        rep["crossScore"] = round(rep["hotScore"] + (cross_count - 1) * 600, 1)
        rep["relatedItems"] = members if len(members) > 1 else []
        rep["isSensitive"] = any(m["isSensitive"] for m in members)
        rep["isNsfw"] = any(m.get("isNsfw") for m in members)
        rep["isPolitics"] = any(m.get("isPolitics") for m in members) or rep.get("mood") == "politics_conflict"
        rep["isSports"] = any(m.get("isSports") for m in members) or rep.get("mood") == "sports"

        ages = [m["ageMinutes"] for m in members if isinstance(m.get("ageMinutes"), int)]
        if cross_count >= 2 and len(ages) >= 2:
            spread = max(ages) - min(ages)
            rep["spreadMinutes"] = spread
            if spread < 60:
                rep["spreadLabel"] = f"⚡ {max(5, spread)}분 만에 {cross_count}곳"
            elif spread <= 720:
                rep["spreadLabel"] = f"⚡ {max(1, round(spread / 60))}시간 내 {cross_count}곳"
            else:
                rep["spreadLabel"] = f"🔥 {cross_count}곳 동시 화제"
        elif cross_count >= 2:
            rep["spreadMinutes"] = None
            rep["spreadLabel"] = f"🔥 {cross_count}곳 동시 화제"
        else:
            rep["spreadMinutes"] = None
            rep["spreadLabel"] = ""

        result.append(rep)

    result.sort(key=lambda x: x["crossScore"], reverse=True)
    return result


def call_deepseek(messages: list[dict], api_key: str, max_tokens: int = 2400) -> str:
    payload = {
        "model": "deepseek-chat",
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def load_previous_cache(out_path: Path) -> dict[str, dict]:
    cache: dict[str, dict] = {}
    if not out_path.exists():
        return cache
    try:
        old = json.loads(out_path.read_text(encoding="utf-8"))
        for it in old.get("items", []):
            if it.get("aiSummaryTitle"):
                cache[it["url"]] = {
                    "aiSummaryTitle": it.get("aiSummaryTitle"),
                    "aiThreeLineSummary": it.get("aiThreeLineSummary"),
                    "mood": it.get("mood"),
                    "isSensitive": it.get("isSensitive"),
                    "opinionCompare": it.get("opinionCompare"),
                }
    except Exception:
        pass
    return cache


def enrich_with_ai(items: list[dict], out_path: Path, api_key: str) -> tuple[list[dict], list[dict]]:
    cache = load_previous_cache(out_path)
    for it in items:
        cached = cache.get(it["url"])
        if cached:
            it["aiSummaryTitle"] = cached["aiSummaryTitle"]
            it["aiThreeLineSummary"] = cached.get("aiThreeLineSummary") or []
            if cached.get("mood"):
                it["mood"] = cached["mood"]
            if cached.get("isSensitive") is not None:
                it["isSensitive"] = cached["isSensitive"]
            if cached.get("opinionCompare"):
                it["opinionCompare"] = cached["opinionCompare"]

    # Enrich top 28 issue items that lack AI summary
    targets = [
        it for it in items
        if it["category"] == "issue" and not it.get("aiSummaryTitle")
    ][:28]

    for i in range(0, len(targets), 14):
        batch = targets[i : i + 14]
        prompt_items = [
            {
                "id": it["id"],
                "source": it["source"],
                "title": it["title"],
                "communities": it.get("communities", [it["source"]]),
                "relatedTitles": [m["title"] for m in it.get("relatedItems", [])][:4],
            }
            for it in batch
        ]
        sys_msg = (
            "너는 한국 커뮤니티 큐레이션 에디터다. 각 게시글 제목(및 묶인 커뮤니티 제목)을 보고 JSON으로 응답하라.\n"
            "응답 형식: {\"items\": [{\"id\": \"...\", \"aiSummaryTitle\": \"낚시성 제거한 명확한 1줄 보조 제목(28자 이내)\", "
            "\"aiThreeLineSummary\": [\"핵심 맥락 1\", \"핵심 포인트 2\", \"시사점/주의점 3\"], "
            "\"mood\": \"humor|info|it_econ|sports|life|politics_conflict\", "
            "\"isSensitive\": true/false, "
            "\"opinionCompare\": \"2곳 이상 동시 화제인 경우 커뮤니티별 반응 차이 1줄 요약(단독 글이면 빈 문자열)\"}]}\n"
            "isSensitive는 정치인/정당/선거/혐오/갈등/성범죄/선정성/자극적 사건사고면 true, 일반 유머/생활/IT/스포츠면 false."
        )
        try:
            raw = call_deepseek(
                [
                    {"role": "system", "content": sys_msg},
                    {"role": "user", "content": json.dumps(prompt_items, ensure_ascii=False)},
                ],
                api_key,
            )
            parsed = json.loads(raw)
            by_id = {x["id"]: x for x in parsed.get("items", []) if isinstance(x, dict) and x.get("id")}
            for it in batch:
                res = by_id.get(it["id"])
                if res:
                    it["aiSummaryTitle"] = clean_text(res.get("aiSummaryTitle"))
                    it["aiThreeLineSummary"] = [clean_text(s) for s in (res.get("aiThreeLineSummary") or []) if clean_text(s)][:3]
                    if res.get("mood") in {"humor", "info", "it_econ", "sports", "life", "politics_conflict"}:
                        it["mood"] = res["mood"]
                    if isinstance(res.get("isSensitive"), bool):
                        it["isSensitive"] = res["isSensitive"]
                    if clean_text(res.get("opinionCompare")):
                        it["opinionCompare"] = clean_text(res.get("opinionCompare"))
        except Exception as exc:
            print("AI batch enrich skipped:", exc)

    # Generate Top 10 3-minute briefing
    top10_src = [it for it in items if it["category"] == "issue"][:10]
    briefing: list[dict] = []
    if top10_src:
        try:
            b_input = [
                {
                    "id": it["id"],
                    "clusterId": it["clusterId"],
                    "title": it.get("aiSummaryTitle") or it["title"],
                    "rawTitle": it["title"],
                    "communities": it.get("communities", [it["source"]]),
                    "mood": it.get("mood", "humor"),
                }
                for it in top10_src
            ]
            b_sys = (
                "너는 출퇴근 3분 브리핑 에디터다. 상위 인기 이슈 10개를 카드 뉴스 형식으로 정리해 JSON으로 답하라.\n"
                "응답 형식: {\"briefing\": [{\"id\": \"...\", \"tag\": \"분야 한단어(예: IT·경제, 유머, 사회)\", "
                "\"headline\": \"한눈에 들어오는 헤드라인(25자 이내)\", \"summary\": \"왜 화제인지 핵심 1~2문장(70자 이내)\"}]}"
            )
            raw_b = call_deepseek(
                [
                    {"role": "system", "content": b_sys},
                    {"role": "user", "content": json.dumps(b_input, ensure_ascii=False)},
                ],
                api_key,
                max_tokens=1600,
            )
            parsed_b = json.loads(raw_b)
            src_map = {it["id"]: it for it in top10_src}
            for row in parsed_b.get("briefing", [])[:10]:
                src = src_map.get(row.get("id"))
                if not src:
                    continue
                briefing.append({
                    "id": src["id"],
                    "clusterId": src["clusterId"],
                    "tag": clean_text(row.get("tag")) or "이슈",
                    "headline": clean_text(row.get("headline")) or src["title"],
                    "summary": clean_text(row.get("summary")) or (src.get("aiSummaryTitle") or ""),
                    "url": src["url"],
                    "communities": src.get("communities", [src["source"]]),
                    "isSensitive": src.get("isSensitive", False),
                    "isNsfw": src.get("isNsfw", False),
                    "isPolitics": src.get("isPolitics", False),
                    "isSports": src.get("isSports", False),
                })
        except Exception as exc:
            print("AI briefing skipped:", exc)

    if not briefing and top10_src:
        for it in top10_src:
            briefing.append({
                "id": it["id"],
                "clusterId": it["clusterId"],
                "tag": it["source"],
                "headline": it.get("aiSummaryTitle") or it["title"],
                "summary": " · ".join(it.get("aiThreeLineSummary") or []) or it["title"],
                "url": it["url"],
                "communities": it.get("communities", [it["source"]]),
                "isSensitive": it.get("isSensitive", False),
                "isNsfw": it.get("isNsfw", False),
                "isPolitics": it.get("isPolitics", False),
                "isSports": it.get("isSports", False),
            })

    return items, briefing


def main() -> None:
    collectors = [
        ("클리앙", fetch_clien_park),
        ("보배드림", fetch_bobaedream),
        ("SLR클럽", fetch_slrclub),
        ("웃긴대학", fetch_humoruniv),
        ("뽐뿌", fetch_ppomppu_deal_rss),
        ("클리앙 알뜰", fetch_clien_jirum),
        ("다모앙 알뜰", fetch_damoang_deal),
    ]
    all_items = []
    stats = {}
    for name, fn in collectors:
        try:
            res = fn()
            stats[name] = len(res)
            all_items.extend(res)
        except Exception as exc:
            stats[name] = f"err: {exc}"

    clustered = cluster_items(all_items)
    out = Path(__file__).parent / "data.json"
    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    briefing: list[dict] = []

    if api_key:
        clustered, briefing = enrich_with_ai(clustered, out, api_key)
    else:
        top10_src = [it for it in clustered if it["category"] == "issue"][:10]
        briefing = [
            {
                "id": it["id"],
                "clusterId": it["clusterId"],
                "tag": it["source"],
                "headline": it["title"],
                "summary": f"{', '.join(it.get('communities', [it['source']]))} 화제글",
                "url": it["url"],
                "communities": it.get("communities", [it["source"]]),
                "isSensitive": it.get("isSensitive", False),
            }
            for it in top10_src
        ]

    payload = {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "ai_enabled": bool(api_key),
        "stats": stats,
        "briefing": briefing,
        "items": clustered,
    }
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved", out, "clusters:", len(clustered), "ai_enabled:", bool(api_key), "stats:", stats)


if __name__ == "__main__":
    main()
