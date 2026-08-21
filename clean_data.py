# -*- coding: utf-8 -*-
"""
이미 수집된 crawl_data/*.csv 파일에 is_excluded / exclude_reason 컬럼을 추가/갱신한다.
(예: CPU를 먼저 수집했는데 나중에 제외 규칙을 추가한 경우, 재크롤링 없이 이 스크립트만 재실행)

사용법:
    python clean_data.py            # crawl_data/ 안의 모든 csv 처리
    python clean_data.py CPU        # CPU.csv만 처리
"""

import csv
import os
import sys

from exclude_rules import classify_product

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "crawl_data")


def clean_file(filepath: str) -> None:
    with open(filepath, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    if not rows:
        print(f"  - {os.path.basename(filepath)}: 빈 파일, 건너뜀")
        return

    if "is_excluded" not in fieldnames:
        fieldnames = fieldnames + ["is_excluded", "exclude_reason"]

    excluded_count = 0
    for row in rows:
        price = int(row.get("price", 0) or 0)
        is_excluded, reason = classify_product(row.get("name", ""), price, spec=row.get("spec", ""))
        row["is_excluded"] = is_excluded
        row["exclude_reason"] = reason
        if is_excluded:
            excluded_count += 1

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  - {os.path.basename(filepath)}: 총 {len(rows)}개 중 {excluded_count}개 제외 태깅 완료")


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if not os.path.isdir(OUTPUT_DIR):
        print(f"crawl_data 폴더가 없습니다: {OUTPUT_DIR}")
        return

    for filename in os.listdir(OUTPUT_DIR):
        if not filename.endswith(".csv"):
            continue
        category_name = filename[:-4]
        if target and category_name != target:
            continue

        filepath = os.path.join(OUTPUT_DIR, filename)
        print(f"[정제] {filename}")
        clean_file(filepath)


if __name__ == "__main__":
    main()
