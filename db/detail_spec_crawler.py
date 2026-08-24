# -*- coding: utf-8 -*-
"""
다나와 상품 "상세페이지" 스펙 크롤러.

danawa_crawler.py(목록 페이지)와 다른 점:
    - 목록 페이지는 카테고리당 몇 번의 요청으로 수십~수백 개 상품을 한 번에 가져오지만,
      상세페이지는 상품 1개당 요청 1번이 필요하다. 상품 수가 많아서(현재 1500개 이상)
      매일 전체를 다시 긁으면 시간이 오래 걸리고 다나와에도 부담이 된다.
    - 그래서 이 크롤러는 "이미 상세 스펙을 가져온 상품코드"를 캐시 CSV
      (crawl_data/detail_spec_cache.csv)에 기록해두고, 다음 실행부터는
      캐시에 없는 새 상품코드만 크롤링한다 (증분 방식).
    - 상세 스펙은 가격과 달리 거의 안 바뀌는 정보(길이, 규격 등)라서
      매일 갱신할 필요가 없다는 전제.

사용법:
    python db/detail_spec_crawler.py            # 전체 카테고리, 새 상품코드만
    python db/detail_spec_crawler.py 케이스      # 케이스 카테고리만
    python db/detail_spec_crawler.py --force     # 캐시 무시하고 전부 재수집
"""

import csv
import os
import sys
import time

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from detail_spec_parser import parse_detail_spec  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL_DATA_DIR = os.path.join(BASE_DIR, "crawl_data")
CACHE_FILE = os.path.join(CRAWL_DATA_DIR, "detail_spec_cache.csv")

MARKET_PLACE_SEQ = 16
REQUEST_DELAY_SEC = 2

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "X-Requested-With": "XMLHttpRequest",
}

CATEGORIES = ["CPU", "그래픽카드", "메인보드", "RAM", "SSD", "HDD", "쿨러", "파워", "케이스"]


def fetch_detail(session: requests.Session, product_id: int) -> str:
    url = "https://shop.danawa.com/pc/"
    params = {
        "controller": "estimateDeal",
        "methods": "productInformation",
        "productSeq": product_id,
        "marketPlaceSeq": MARKET_PLACE_SEQ,
    }
    resp = session.get(url, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def load_target_product_ids(category: str) -> set:
    """crawl_data/{카테고리}.csv 에서 is_excluded=False인 상품코드만 모은다."""
    csv_path = os.path.join(CRAWL_DATA_DIR, f"{category}.csv")
    if not os.path.isfile(csv_path):
        return set()
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = csv.DictReader(f)
        return {int(r["code"]) for r in rows if r.get("is_excluded") == "False"}


def load_cache() -> dict:
    """이미 수집한 (category, product_id) -> 전체 스펙 dict. 캐시 파일이 없으면 빈 dict."""
    cache = {}
    if not os.path.isfile(CACHE_FILE):
        return cache
    with open(CACHE_FILE, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = (row["category"], int(row["product_id"]))
            cache[key] = row
    return cache


def append_to_cache(rows: list) -> None:
    if not rows:
        return
    os.makedirs(CRAWL_DATA_DIR, exist_ok=True)
    file_exists = os.path.isfile(CACHE_FILE)
    fieldnames = ["category", "product_id", "spec_json"]
    with open(CACHE_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def main():
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    target_category = args[0] if args else None

    cache = {} if force else load_cache()
    session = requests.Session()

    new_rows = []

    categories = [target_category] if target_category else CATEGORIES

    for category in categories:
        if category not in CATEGORIES:
            print(f"[건너뜀] 알 수 없는 카테고리: {category}")
            continue

        product_ids = load_target_product_ids(category)
        already_cached = {pid for (cat, pid) in cache if cat == category}
        to_fetch = sorted(product_ids - already_cached)

        print(f"[{category}] 대상 {len(product_ids)}개 중 신규 {len(to_fetch)}개 크롤링 예정")

        for i, product_id in enumerate(to_fetch, 1):
            print(f"  ({i}/{len(to_fetch)}) {category} {product_id} 요청 중...")
            try:
                html = fetch_detail(session, product_id)
                spec = parse_detail_spec(html)
            except requests.RequestException as e:
                print(f"    ! 요청 실패: {e}")
                continue
            except Exception as e:
                print(f"    ! 파싱 실패: {e}")
                continue

            import json
            new_rows.append({
                "category": category,
                "product_id": product_id,
                "spec_json": json.dumps(spec, ensure_ascii=False),
            })

            time.sleep(REQUEST_DELAY_SEC)

    append_to_cache(new_rows)
    print(f"\n총 {len(new_rows)}개 상품 상세 스펙 신규 수집 완료 ({CACHE_FILE})")


if __name__ == "__main__":
    main()
