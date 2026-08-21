# -*- coding: utf-8 -*-
"""
크롤링 대상 카테고리 / 브랜드(제조사코드) 설정.

모든 값은 실제로 F12 Network 탭에서 캡처하고, 응답 데이터로 브랜드가
정확히 필터링되는지 육안으로 검증한 값이다.

필터 방식은 카테고리마다 두 가지가 있다:

1) filter_type="maker"  : 대부분의 카테고리. makerCode[] 파라미터로 제조사 필터.
2) filter_type="attribute": 그래픽카드 전용. 다나와가 그래픽카드는
   "제조사"(보드파트너, 예: ASUS/MSI/PALIT...) 와 "칩셋 제조사"(NVIDIA/AMD/Intel)를
   따로 구분해서 필터링한다. 우리가 원하는 건 일반 소비자용 지포스 카드이므로
   "제조사=NVIDIA"가 아니라 "칩셋 제조사=NVIDIA"를 써야 한다.
   (제조사=NVIDIA로 필터링하면 RTX PRO/H100 같은 워크스테이션·서버용 카드만 나옴 - 확인됨)
   이 필터는 attribute[]=categorySeq|속성그룹ID|속성값ID|타입 형태의 값을 그대로 사용한다.
"""

MARKET_PLACE_SEQ = 16  # PC견적 서비스 고정값
MAX_PAGE = 20           # 카테고리당 최대 페이지 수
REQUEST_DELAY_SEC = 2   # 요청 간 대기 시간 (크롤링 방지 최소화)

CATEGORIES = {
    "CPU": {
        "categorySeq": 873,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "인텔": 3156,
        },
    },
    "쿨러": {
        "categorySeq": 887,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "PCCOOLER": 90587,
            "DEEPCOOL": 51853,
        },
    },
    "메인보드": {
        "categorySeq": 875,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "MSI": 2904,
            "ASUS": 2869,
            "GIGABYTE": 3148,
        },
    },
    "RAM": {
        "categorySeq": 874,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "삼성전자": 702,
            "TeamGroup": 4142,
        },
    },
    "그래픽카드": {
        "categorySeq": 876,
        "categoryDepth": 2,
        "filter_type": "attribute",
        # "칩셋 제조사 = NVIDIA" 필터. (제조사=NVIDIA 아님! 그건 워크스테이션 라인만 잡힘)
        "attributes": {
            "NVIDIA(칩셋)": "876|654|3518|S",
        },
    },
    "SSD": {
        "categorySeq": 32617,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "삼성전자": 702,
        },
    },
    "HDD": {
        "categorySeq": 877,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "Western Digital": 4213,
            "Seagate": 4202,
        },
    },
    "케이스": {
        "categorySeq": 879,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "darkFlash": 15938410,
            "앱코": 2108,
        },
    },
    "파워": {
        "categorySeq": 880,
        "categoryDepth": 2,
        "filter_type": "maker",
        "makerCodes": {
            "마이크로닉스": 3160,
            "darkFlash": 15938410,
        },
    },
}
