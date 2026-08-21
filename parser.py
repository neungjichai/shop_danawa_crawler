"""
샵다나와 PC견적(virtualestimate) 상품 목록 응답(HTML)을 파싱하는 모듈.

핵심 주의점:
- 응답에는 <table class="tbl_list">가 두 개 들어있다.
  1) <div class="adreader_box"> 안의 table  -> 광고/추천 상품 (브랜드 필터 무시하고 노출됨, 반드시 제외)
  2) 진짜 상품 목록 table (adreader_box 밖에 있는 것)
- 상품 row는 <tr class="productList_상품코드">
- 가격이 없는(판매중지/판매준비) 상품은 input[name=price] 값이 0 -> 스킵
"""

from bs4 import BeautifulSoup

from exclude_rules import classify_product


def parse_product_list(html: str, category_name: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")

    products = []

    # list_tbl_wrap 안의 모든 table.tbl_list 중, adreader_box 안에 있지 않은 것만 사용
    wrap = soup.select_one("div.list_tbl_wrap")
    if wrap is None:
        return products

    for table in wrap.select("table.tbl_list"):
        if table.find_parent("div", class_="adreader_box") is not None:
            continue  # 광고 영역 제외

        for tr in table.select("tbody > tr"):
            # 광고 영역이 아니더라도 혹시 recom_area 클래스가 붙은 행은 방어적으로 제외
            if "recom_area" in (tr.get("class") or []):
                continue

            name_input = tr.select_one('input[name="name"]')
            code_input = tr.select_one('input[name="code"]')
            price_input = tr.select_one('input[name="price"]')
            category_input = tr.select_one('input[name="category"]')

            if not (name_input and code_input and price_input):
                continue

            price = int(price_input.get("value", "0") or "0")
            name = name_input.get("value")

            spec_tag = tr.select_one("div.spec_bg > a.spec")
            img_tag = tr.select_one("div.goods_img_box img")

            is_excluded, exclude_reason = classify_product(
                name, price, spec=spec_tag.get_text(strip=True) if spec_tag else ""
            )

            products.append({
                "category": category_input.get("value") if category_input else category_name,
                "code": code_input.get("value"),
                "name": name,
                "price": price,
                "spec": spec_tag.get_text(strip=True) if spec_tag else "",
                "image_url": img_tag.get("src") if img_tag else "",
                "is_excluded": is_excluded,
                "exclude_reason": exclude_reason,
            })

    return products


if __name__ == "__main__":
    with open("sample_cpu_response.html", encoding="utf-8") as f:
        html = f.read()

    result = parse_product_list(html, "CPU")
    print(f"파싱된 상품 수: {len(result)}개\n")
    for p in result:
        print(p)
