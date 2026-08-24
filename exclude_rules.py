# -*- coding: utf-8 -*-
"""
'제외 대상' 판정 규칙.

크롤러/정제 스크립트 양쪽에서 공용으로 사용한다.
여기서 정의한 규칙에 걸리면 데이터를 버리지 않고,
is_excluded=True / exclude_reason=사유 로 태깅만 한다.
(실제 사용 여부는 이 데이터를 소비하는 쪽에서 판단)
"""

import re


# 상품명에 이 키워드가 포함되면 제외 사유로 태깅한다.
NAME_KEYWORD_RULES = {
    "중고": ["(중고)", "중고]", "중고 ("],
    "해외구매": ["(해외구매)", "(직구)", "해외구매]", "직구]", "병행수입"],
    "서버/워크스테이션": ["서버용", "워크스테이션", "(서버)", "RTX PRO", "RTX A", "RTX 6000", "Quadro", "Tesla", "H100", "A100"],
}




# 카테고리별로 spec 맨 앞 토큰이 특정 값으로 "시작해야만" 진짜 대상 부품으로 본다.
# 다나와가 "쿨러/튜닝" 카테고리 안에 액세서리(케이스팬, 써멀컴파운드, 팬허브,
# 써멀 페이스트 가드, HDD 쿨러 등)를 같이 섞어서 보여주기 때문에 필요하다.
CATEGORY_REQUIRED_SPEC_PREFIX = {
    "쿨러": ["CPU 쿨러"],
}


def _spec_fails_category_requirement(category: str, spec: str) -> bool:
    """이 카테고리에 필수 스펙 접두사 규칙이 있는데, spec이 그걸 만족 못 하면 True."""
    required = CATEGORY_REQUIRED_SPEC_PREFIX.get(category)
    if not required or not spec:
        return False
    first_token = spec.split("/")[0].strip()
    return not any(first_token.startswith(p) for p in required)


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


def _spec_has_enterprise_tag(spec: str) -> bool:
    """
    spec 필드에서 '기업용/서버용/워크스테이션용'이 실제로 상품 자체의 용도 태그인지 판별한다.
    _spec_has_laptop_tag와 동일한 방식(맨 앞 토큰 또는 괄호 표기) -- 예: "HDD (기업용)/..."
    """
    if not spec:
        return False
    if re.search(r"\((기업용|서버용|워크스테이션용)\)", spec):
        return True
    first_token = spec.split("/")[0].strip()
    if any(first_token.startswith(tag) for tag in ("기업용", "서버용", "워크스테이션용")):
        return True
    return False


# 케이스처럼 정상 접두사가 다양한(ATX/M-ATX/미니ITX/튜닝 케이스 등) 카테고리는
# "이건 허용" 화이트리스트 대신 "이건 확실히 액세서리" 블랙리스트로 판별하는 게 더 안전하다.
CATEGORY_EXCLUDED_SPEC_PREFIX = {
    "케이스": ["액세서리"],
}


def _spec_is_blacklisted_prefix(category: str, spec: str) -> bool:
    excluded = CATEGORY_EXCLUDED_SPEC_PREFIX.get(category)
    if not excluded or not spec:
        return False
    first_token = spec.split("/")[0].strip()
    return any(first_token == p for p in excluded)


def classify_product(name: str, price: int, spec: str = "", category: str = "") -> tuple[bool, str]:
    """
    상품명/가격/스펙/카테고리를 보고 (is_excluded, exclude_reason)을 반환한다.
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

    if "서버/워크스테이션" not in reasons and _spec_has_enterprise_tag(spec):
        reasons.append("서버/워크스테이션")

    if _spec_fails_category_requirement(category, spec):
        reasons.append("액세서리(대상부품아님)")

    if _spec_is_blacklisted_prefix(category, spec):
        reasons.append("액세서리(대상부품아님)")

    is_excluded = len(reasons) > 0
    return is_excluded, ",".join(reasons)
