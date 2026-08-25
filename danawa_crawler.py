# -*- coding: utf-8 -*-
"""
샵다나와 PC견적(virtualestimate) 상품 크롤러.

사용법:
    python danawa_crawler.py

동작:
    - config.py에 정의된 카테고리 x 브랜드 조합으로 1~MAX_PAGE 페이지까지 순회
    - 요청 사이 REQUEST_DELAY_SEC(기본 2초) 대기
    - 결과를 crawl_data/{카테고리}.csv 에 이어쓰기(append) 저장
    - 각 행에는 crawl_date(수집 날짜, KST 기준) 컬럼이 붙는다 -> 하루 1회 실행 시 날짜별 가격 추이 누적

주의:
    - config.py에서 categorySeq 또는 makerCode가 None인 카테고리/브랜드는 자동으로 건너뛴다.
    - 실행 전에 config.py의 TODO 항목을 실제 값으로 채워야 한다.
"""

import csv
import os
import time
from datetime import datetime, timezone, timedelta

import requests

from config import CATEGORIES, MARKET_PLACE_SEQ, MAX_PAGE, REQUEST_DELAY_SEC
from parser import parse_product_list

BASE_URL = "https://shop.danawa.com/virtualestimate/"
INDEX_REFERER = f"{BASE_URL}?controller=estimateMain&methods=index&marketPlaceSeq={MARKET_PLACE_SEQ}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": INDEX_REFERER,
    "X-Requested-With": "XMLHttpRequest",
}

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl_data")

KST = timezone(timedelta(hours=9))


def build_params(category_seq: int, category_depth: int, page: int,
                  maker_codes: list[int] | None = None,
                  attributes: list[str] | None = None) -> list:
    """
    requests가 makerCode[]=A&makerCode[]=B (또는 attribute[]=...) 형태로 보낼 수 있도록
    파라미터를 dict가 아니라 튜플 리스트로 구성한다.

    maker_codes: 제조사 필터 (대부분의 카테고리)
    attributes: 속성 필터 (그래픽카드의 "칩셋 제조사" 필터 등, categorySeq|그룹ID|값ID|타입 형식 문자열 그대로 사용)
    """
    params = [
        ("controller", "estimateMain"),
        ("methods", "product"),
        ("marketPlaceSeq", MARKET_PLACE_SEQ),
        ("categorySeq", category_seq),
        ("categoryDepth", category_depth),
        ("pseq", 2),  # Network 캡처에서 관찰된 고정값. 정확한 의미는 불명이나 실제 요청을 그대로 재현.
        ("orderbyList", "PRODUCT_POPULAR_DESC"),
        ("page", page),
        ("minPrice", 0),
        ("maxPrice", 0),
    ]
    for code in (maker_codes or []):
        params.append(("makerCode[]", code))
    for attr in (attributes or []):
        params.append(("attribute[]", attr))
    return params


def fetch_page(session: requests.Session, category_seq: int, category_depth: int, page: int,
               maker_codes: list[int] | None = None,
               attributes: list[str] | None = None) -> str:
    params = build_params(category_seq, category_depth, page,
                           maker_codes=maker_codes, attributes=attributes)
    resp = session.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    return resp.text


def save_to_csv(category_name: str, rows: list[dict]) -> None:
    """
    crawl_data/{카테고리}.csv 에 저장한다.

    같은 날짜(crawl_date)로 재실행하는 경우를 대비해:
    - 기존 파일에서 '오늘 날짜' 행은 전부 제거하고
    - 이번에 새로 수집한 행으로 교체한다 (하루 1회 실행 시 스냅샷 1개만 유지)
    - 다른 날짜의 과거 데이터는 그대로 보존 (날짜별 가격 추이 누적 목적)

    -> 하루에 여러 번 실행해도 중복이 쌓이지 않고, 마지막 실행 결과로 항상 깨끗하게 정리된다.
    """
    if not rows:
        return

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    filepath = os.path.join(OUTPUT_DIR, f"{category_name}.csv")

    fieldnames = ["crawl_date", "category", "maker", "code", "name", "price", "spec", "image_url",
                  "is_excluded", "exclude_reason"]

    today = rows[0]["crawl_date"]  # 이번 실행에서 수집한 데이터는 전부 같은 날짜

    existing_rows = []
    removed = 0
    if os.path.isfile(filepath):
        with open(filepath, encoding="utf-8-sig") as f:
            all_existing = list(csv.DictReader(f))
        existing_rows = [r for r in all_existing if r.get("crawl_date") != today]
        removed = len(all_existing) - len(existing_rows)

    if removed:
        print(f"    (기존 {today} 데이터 {removed}개 발견 - 재실행으로 판단, 새 결과로 교체)")

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
        writer.writerows(rows)


def crawl_category(session: requests.Session, category_name: str, category_info: dict) -> None:
    category_seq = category_info.get("categorySeq")
    if category_seq is None:
        print(f"[건너뜀] {category_name}: categorySeq 미설정 (config.py 확인 필요)")
        return

    category_depth = category_info.get("categoryDepth", 2)
    max_page = category_info.get("max_page", MAX_PAGE)  # 카테고리별 override, 없으면 전역 기본값
    sub_requests = category_info.get("requests", [])

    if not sub_requests:
        print(f"[건너뜀] {category_name}: requests 미설정 (config.py 확인 필요)")
        return

    crawl_date = datetime.now(KST).strftime("%Y-%m-%d")

    all_rows = []
    seen_codes = set()  # 카테고리 전체에서 중복 상품코드 방지 (여러 요청에 걸쳐 겹칠 수 있음)

    for req in sub_requests:
        label = req.get("label", "")
        maker_codes_map = req.get("makerCodes", {})
        attr_map = req.get("attributes", {})

        maker_codes = [code for code in maker_codes_map.values() if code is not None] or None
        attributes = [value for value in attr_map.values() if value] or None

        if not maker_codes and not attributes:
            print(f"  [건너뜀] {category_name} - {label}: makerCode/attribute 둘 다 미설정")
            continue

        for page in range(1, max_page + 1):
            print(f"  - {category_name} ({label}) {page}페이지 요청 중...")
            try:
                html = fetch_page(session, category_seq, category_depth, page,
                                   maker_codes=maker_codes, attributes=attributes)
            except requests.RequestException as e:
                print(f"    ! 요청 실패: {e}")
                break

            products = parse_product_list(html, category_name)

            if not products:
                print(f"    - {page}페이지에 상품 없음. 이 요청 크롤링 종료.")
                break

            new_count = 0
            for p in products:
                if p["code"] in seen_codes:
                    continue
                seen_codes.add(p["code"])
                p["crawl_date"] = crawl_date
                p["maker"] = label
                all_rows.append(p)
                new_count += 1

            print(f"    - {new_count}개 수집 (누적 {len(all_rows)}개)")

            time.sleep(REQUEST_DELAY_SEC)

    save_to_csv(category_name, all_rows)
    print(f"  => {category_name} 완료: 총 {len(all_rows)}개 저장 ({category_name}.csv)")


def main():
    session = requests.Session()
    # index 페이지를 한 번 먼저 방문해 세션/쿠키를 확보 (referer 신뢰도 향상)
    try:
        session.get(INDEX_REFERER, headers=HEADERS, timeout=15)
        time.sleep(REQUEST_DELAY_SEC)
    except requests.RequestException as e:
        print(f"[경고] 초기 세션 확보 실패: {e}")

    for category_name, category_info in CATEGORIES.items():
        print(f"\n[시작] {category_name}")
        crawl_category(session, category_name, category_info)


if __name__ == "__main__":
    main()
