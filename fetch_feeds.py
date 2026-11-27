#!/usr/bin/env python3
"""Fetch Korean community hot issues and hot deals into data.json."""

from __future__ import annotations

import json
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
        # Remove trailing [N] comment count from title if glued
        title = re.sub(r"\s*\[\d+\]\s*$", "", title)
        link = href if href.startswith("http") else "https://web.humoruniv.com/board/humor/" + href.lstrip("/")
        reply = parse_int("".join(row.xpath(".//span[contains(@class,'list_comment_num')]/text()")))
        views = parse_int("".join(row.xpath(".//td[contains(@class,'li_und')][1]/text()")))
        likes = parse_int("".join(row.xpath(".//td[contains(@class,'li_und')][2]//span/text()")))
        date_str = clean_text("".join(row.xpath(".//td[contains(@class,'li_date')]/text()")))
        items.append({
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
        # Strip leading status badges like "6 진행중"
        txt = re.sub(r"^\d+\s*(진행중|종료|품절)\s*", "", txt)
        txt = re.sub(r"\s+N\s+.*$", "", txt)
        if len(txt) < 5:
            continue
        seen.add(href)
        link = href if href.startswith("http") else "https://damoang.net" + href
        items.append({
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

    payload = {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M KST"),
        "stats": stats,
        "items": all_items,
    }
    out = Path(__file__).parent / "data.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved", out, "stats:", stats)


if __name__ == "__main__":
    main()
