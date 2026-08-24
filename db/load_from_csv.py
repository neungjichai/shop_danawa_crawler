# -*- coding: utf-8 -*-
"""
danawa_crawler.py가 만든 crawl_data/*.csv를 읽어서
db/schema.sql(기존 DB 프로젝트에서 그대로 가져온 스키마)에 적재한다.

기존 프로젝트(danawa_only_load.sql)와의 차이:
    - 기존: www.danawa.com을 Selenium으로 긁은 "가로형(날짜가 컬럼)" CSV를
      MySQL LOAD DATA INFILE로 적재 -> SQL 안에서 unpivot
    - 지금: shop.danawa.com/virtualestimate API를 직접 호출하는
      "세로형(crawl_date가 행)" CSV를 Python에서 직접 파싱 후 INSERT

호환성 컬럼(socket, capacity_gb, ram_type 등)은 상세페이지 스크래퍼가 없으므로
db/spec_parser.py가 목록 페이지 spec 텍스트에서 정규식으로 추출해 채운다.
일부 필드(RAM 방열판 높이 등 상세페이지 전용 정보)는 지금 단계에서는 NULL로 남는다.

사용법:
    (환경변수로 DB 접속정보 지정 후)
    python db/load_from_csv.py
"""

import csv
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec_parser import PARSERS  # noqa: E402

CRAWL_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "crawl_data")

# (CSV 파일명, 테이블 접두어) — schema.sql의 테이블명과 반드시 일치해야 한다.
CATEGORY_TABLE_MAP = [
    ("CPU", "cpu"),
    ("그래픽카드", "vga"),
    ("메인보드", "mboard"),
    ("RAM", "ram"),
    ("SSD", "ssd"),
    ("HDD", "hdd"),
    ("쿨러", "cooler"),
    ("파워", "power"),
    ("케이스", "case"),
]

KST = timezone(timedelta(hours=9))

# 목록 페이지 URL 재구성이 안 되므로(상세페이지 상품URL은 크롤러가 수집 안 함),
# product_media.product_url은 다나와 상품코드 기반 표준 URL 패턴으로 채운다.
DANAWA_PRODUCT_URL_TEMPLATE = "https://prod.danawa.com/info/?pcode={code}"


def _read_kept_rows(csv_path: str) -> list[dict]:
    """is_excluded=False인 행만 읽는다."""
    if not os.path.isfile(csv_path):
        print(f"  ! 파일 없음: {csv_path} (건너뜀)")
        return []
    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    return [r for r in rows if r.get("is_excluded") == "False"]


def _usage_type(category_name: str, name: str, spec: str) -> str:
    """
    기존 generate_sql.py의 USAGE_TYPE_SQL 규칙을 파이썬으로 재현.
    (제조사를 이미 크롤링 단계에서 제한했기 때문에 대부분 'consumer'로 나오는 게 정상.)
    """
    if category_name == "CPU":
        if "EPYC" in name or "Xeon" in name or "제온" in name:
            return "server"
        return "consumer"
    if category_name == "그래픽카드":
        if "RTX PRO" in name or "Quadro" in name or "Tesla" in name:
            return "workstation"
        return "gaming"
    if category_name == "HDD":
        return "nas" if "NAS용" in spec else "consumer"
    if category_name == "메인보드":
        return "consumer"
    return "consumer"


def build_insert_statements(conn) -> None:
    """conn: mysql.connector connection. 카테고리별로 products/prices/product_media를 채운다."""
    cursor = conn.cursor()
    crawl_dt = datetime.now(KST)

    for category_name, prefix in CATEGORY_TABLE_MAP:
        csv_path = os.path.join(CRAWL_DATA_DIR, f"{category_name}.csv")
        rows = _read_kept_rows(csv_path)
        if not rows:
            continue

        parser = PARSERS.get(category_name)
        product_rows = []
        price_rows = []
        media_rows = []

        seen_ids = set()
        for r in rows:
            product_id = int(r["code"])
            if product_id in seen_ids:
                continue  # 같은 실행 내 중복 상품코드 방지
            seen_ids.add(product_id)

            parsed = parser(r["name"], r["spec"]) if parser else {}
            usage_type = _usage_type(category_name, r["name"], r["spec"])
            company = r.get("maker", "")

            product_rows.append((product_id, r["name"], company, usage_type, parsed))
            price_rows.append((product_id, crawl_dt, r["name"][:300], int(r["price"])))
            media_rows.append((category_name, product_id, r.get("image_url", ""),
                                DANAWA_PRODUCT_URL_TEMPLATE.format(code=product_id)))

        _upsert_products(cursor, prefix, category_name, product_rows)
        _insert_prices(cursor, prefix, price_rows)
        _upsert_media(cursor, media_rows)

        conn.commit()
        print(f"  {category_name}: 상품 {len(product_rows)}개 / 가격 {len(price_rows)}건 적재 완료")


# 카테고리별 products 테이블의 호환성 컬럼 순서 (schema.sql과 반드시 일치)
COMPAT_COLUMNS = {
    "cpu": ["socket", "has_igpu", "power_min_w", "power_max_w"],
    "vga": ["length_mm", "recommended_psu_w", "power_connector"],
    "mboard": ["ram_slot_count", "socket", "form_factor", "ram_type"],
    "ram": ["ram_type", "capacity_gb", "speed_mhz"],
    "ssd": ["capacity_gb", "interface"],
    "hdd": ["capacity_gb"],
    "cooler": ["support_sockets", "height_mm", "cooler_type", "radiator_mm", "max_tdp_w"],
    "power": ["rated_w", "form_factor"],
    "case": ["support_form_factors", "max_cooler_height_mm", "max_vga_length_mm",
              "support_psu_form_factors", "support_radiator_mm"],
}


def _upsert_products(cursor, prefix: str, category_name: str, product_rows: list) -> None:
    compat_cols = COMPAT_COLUMNS[prefix]
    columns = ["product_id", "name", "company", "usage_type"] + compat_cols
    placeholders = ", ".join(["%s"] * len(columns))
    update_clause = ", ".join(f"{c}=VALUES({c})" for c in columns if c != "product_id")

    sql = (
        f"INSERT INTO {prefix}_products ({', '.join(columns)}) VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {update_clause}"
    )

    values = []
    for product_id, name, company, usage_type, parsed in product_rows:
        row = [product_id, name, company, usage_type] + [parsed.get(c) for c in compat_cols]
        values.append(tuple(row))

    if values:
        cursor.executemany(sql, values)


def _insert_prices(cursor, prefix: str, price_rows: list) -> None:
    sql = f"INSERT INTO {prefix}_prices (product_id, crawl_date, option_name, price) VALUES (%s, %s, %s, %s)"
    if price_rows:
        cursor.executemany(sql, price_rows)


def _upsert_media(cursor, media_rows: list) -> None:
    sql = (
        "INSERT INTO product_media (category, product_id, image_url, product_url) "
        "VALUES (%s, %s, %s, %s) "
        "ON DUPLICATE KEY UPDATE image_url=VALUES(image_url), product_url=VALUES(product_url)"
    )
    if media_rows:
        cursor.executemany(sql, media_rows)


def main():
    import mysql.connector

    config = {
        "host": os.environ.get("DANAWA_DB_HOST", "localhost"),
        "port": int(os.environ.get("DANAWA_DB_PORT", "3306")),
        "user": os.environ.get("DANAWA_DB_USER", "root"),
        "password": os.environ.get("DANAWA_DB_PASSWORD", ""),
        "database": os.environ.get("DANAWA_DB_NAME", "shop_danawa"),
        "charset": "utf8mb4",
    }

    conn = mysql.connector.connect(**config)
    try:
        build_insert_statements(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
