# -*- coding: utf-8 -*-
"""
다나와 상품 상세페이지의 "상품 상세 스펙" 표(spec_tbl)를 파싱하는 모듈.

엔드포인트: https://shop.danawa.com/pc/?controller=estimateDeal&methods=productInformation
            &productSeq={product_id}&marketPlaceSeq=16

목록 페이지 spec(슬래시로 이어붙인 한 줄 텍스트)보다 훨씬 상세하고,
<th class="tit">라벨</th><td class="dsc">값</td> 쌍이 반복되는 HTML 표 구조라 파싱이 정확하다.

주의: 섹션 제목 행(<th scope="row" colspan="4">[호환성]</th>)은 라벨-값 쌍이 아니라
섹션 구분자이므로 걸러야 한다 (colspan 속성으로 구분 가능).
"""

from bs4 import BeautifulSoup


def parse_detail_spec(html: str) -> dict:
    """
    상세페이지 응답 HTML에서 전체 라벨-값 쌍을 딕셔너리로 추출한다.
    같은 라벨이 여러 번 나오면(드묾) 마지막 값으로 덮어쓴다.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.spec_tbl")
    if table is None:
        return {}

    result = {}
    for tr in table.select("tbody > tr"):
        cells = tr.find_all(["th", "td"])
        i = 0
        while i < len(cells) - 1:
            th, td = cells[i], cells[i + 1]
            # 섹션 제목 행(th에 colspan 있고 td 없음)은 건너뛴다
            if th.name == "th" and td.name == "td" and not th.has_attr("colspan"):
                label = th.get_text(strip=True)
                value = td.get_text(strip=True)
                if label:
                    result[label] = value
                i += 2
            else:
                i += 1

    return result


def parse_case_radiator_info(detail_spec: dict) -> dict:
    """
    케이스 상세 스펙 딕셔너리에서 라디에이터/수랭 관련 정보만 뽑아 정리한다.
    "최대360mm, 280mm" 같은 콤마 목록에서 가장 큰 값을 대표값으로 취한다.
    """
    def max_mm(value: str):
        if not value:
            return None
        import re
        nums = re.findall(r"(\d+)mm", value)
        return max(int(n) for n in nums) if nums else None

    def slot_count(value: str):
        if not value:
            return None
        import re
        m = re.search(r"(\d+)열", value)
        return int(m.group(1)) if m else None

    return {
        "radiator_top_mm": max_mm(detail_spec.get("라디에이터(상단)", "")),
        "radiator_front_mm": max_mm(detail_spec.get("라디에이터(전면)", "")),
        "radiator_rear_mm": max_mm(detail_spec.get("라디에이터(후면)", "")),
        "radiator_bottom_mm": max_mm(detail_spec.get("라디에이터(하단)", "")),
        "liquid_cooler_slots": slot_count(detail_spec.get("수랭쿨러 규격", "")),
    }


if __name__ == "__main__":
    with open("sample_detail_response.html", encoding="utf-8") as f:
        html = f.read()

    spec = parse_detail_spec(html)
    print("전체 스펙 딕셔너리:")
    for k, v in spec.items():
        print(f"  {k}: {v}")

    print()
    print("케이스 라디에이터 정보:")
    print(parse_case_radiator_info(spec))
