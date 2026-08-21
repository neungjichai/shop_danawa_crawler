# -*- coding: utf-8 -*-
"""
'제외 대상' 판정 규칙.

크롤러/정제 스크립트 양쪽에서 공용으로 사용한다.
여기서 정의한 규칙에 걸리면 데이터를 버리지 않고,
is_excluded=True / exclude_reason=사유 로 태깅만 한다.
(실제 사용 여부는 이 데이터를 소비하는 쪽에서 판단)
"""

# 상품명에 이 키워드가 포함되면 제외 사유로 태깅한다.
NAME_KEYWORD_RULES = {
    "중고": ["(중고)", "중고]", "중고 ("],
    "해외구매": ["(해외구매)", "(직구)", "해외구매]", "직구]", "병행수입"],
    "서버/워크스테이션": ["서버용", "워크스테이션", "(서버)"],
}

# 스펙(spec) 필드에 "서버용/워크스테이션용" 처럼 용도가 명시되는 경우가 있다.
# 이 값으로 판정하는 게 상품명보다 훨씬 확실하다.
# ("노트북용"은 문장 중간에 다른 의미(예: 메인보드의 SO-DIMM 슬롯 설명)로도 등장할 수 있어
#  아래 _spec_has_laptop_tag() 함수로 별도의 정교한 판별을 한다.)
SPEC_KEYWORD_RULES = {
    "서버/워크스테이션": ["서버용", "워크스테이션용"],
}


def _spec_has_laptop_tag(spec: str) -> bool:
    """
    spec 필드에서 '노트북용'이 실제로 상품 자체의 용도 태그인지 판별한다.

    - 맨 앞 토큰이 "노트북용"으로 시작 (예: "노트북용/DDR5/...") -> 진짜 노트북용 부품
    - "(노트북용)" 처럼 괄호로 감싸진 경우 (예: "HDD (노트북용)/...") -> 진짜 노트북용 부품
    - 그 외 문장 중간에 낀 "DDR4 노트북용" 같은 표현 -> 노트북 규격 RAM 슬롯을 지원한다는
      뜻일 뿐 (예: 미니-ITX 메인보드의 SO-DIMM 슬롯), 상품 자체가 노트북용이라는 뜻이 아니므로 제외 안 함
    """
    if not spec:
        return False
    if "(노트북용)" in spec:
        return True
    first_token = spec.split("/")[0].strip()
    if first_token.startswith("노트북용"):
        return True
    return False


def classify_product(name: str, price: int, spec: str = "") -> tuple[bool, str]:
    """
    상품명/가격/스펙을 보고 (is_excluded, exclude_reason)을 반환한다.
    여러 사유에 해당하면 콤마로 이어붙인다.
    """
    reasons = []

    if price <= 0:
        reasons.append("가격정보없음(판매준비/판매중지)")

    for reason, keywords in NAME_KEYWORD_RULES.items():
        for kw in keywords:
            if kw and kw in name:
                reasons.append(reason)
                break

    if _spec_has_laptop_tag(spec):
        reasons.append("노트북용")

    if "서버/워크스테이션" not in reasons:
        for kw in SPEC_KEYWORD_RULES["서버/워크스테이션"]:
            if kw and spec and kw in spec:
                reasons.append("서버/워크스테이션")
                break

    is_excluded = len(reasons) > 0
    return is_excluded, ",".join(reasons)
