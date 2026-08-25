# -*- coding: utf-8 -*-
"""
크롤링 대상 카테고리 / 브랜드(제조사코드) 설정.

모든 값은 실제로 F12 Network 탭에서 캡처하고, 응답 데이터로 브랜드가
정확히 필터링되는지 육안으로 검증한 값이다.

구조: 카테고리 하나 안에 "requests"(요청 목록)를 여러 개 둘 수 있다.
각 요청은 makerCode[]/attribute[] 필터를 독립적으로 가질 수 있다.
-> 예: CPU는 "인텔(makerCode만)" 요청 하나 + "AMD 라이젠5/7(makerCode+attribute)" 요청
       하나, 이렇게 서로 다른 필터 조합을 한 카테고리 안에서 각각 따로 보내야 할 때 필요하다.
       (인텔은 브랜드만 필터링하면 되지만, AMD는 브랜드 필터만으로는 라이젠3/9까지
        다 딸려오기 때문에 attribute[]로 라인업까지 추가로 좁혀야 함)

각 요청 딕셔너리 구조:
    {
        "label": "화면에 표시할 이름 (CSV의 maker 컬럼에 들어감)",
        "makerCodes": {"브랜드명": 코드, ...},   # 없으면 생략 가능
        "attributes": {"속성이름": "categorySeq|그룹ID|값ID|타입", ...},  # 없으면 생략 가능
    }

attribute[]는 그래픽카드/AMD CPU 라인업처럼, 다나와가 "제조사"와 별개로
"칩셋 제조사"나 "CPU 종류" 같은 세부 속성 필터를 따로 두는 경우에 쓴다.
"""

MARKET_PLACE_SEQ = 16  # PC견적 서비스 고정값
MAX_PAGE = 20           # 카테고리당 최대 페이지 수
REQUEST_DELAY_SEC = 2   # 요청 간 대기 시간 (크롤링 방지 최소화)

CATEGORIES = {
    "CPU": {
        "categorySeq": 873,
        "categoryDepth": 2,
        "requests": [
            {
                "label": "인텔",
                "makerCodes": {"인텔": 3156},
            },
            {
                "label": "AMD(라이젠5/7)",
                "makerCodes": {"AMD": 3132},
                # "AMD CPU종류" 필터: 라이젠5/7의 3~6세대만 (라이젠3/9, 스레드리퍼 등 제외)
                "attributes": {
                    "라이젠7-6세대": "873|312287|987841|S",
                    "라이젠5-6세대": "873|312287|706768|S",
                    "라이젠7-5세대": "873|312287|801628|S",
                    "라이젠5-5세대": "873|312287|627623|S",
                    "라이젠7-4세대": "873|312287|987844|S",
                    "라이젠5-4세대": "873|312287|627626|S",
                    "라이젠7-3세대": "873|312287|706771|S",
                    "라이젠5-3세대": "873|312287|801625|S",
                },
            },
        ],
    },
    "쿨러": {
        "categorySeq": 887,
        "categoryDepth": 2,
        "requests": [
            {"label": "PCCOOLER,DEEPCOOL", "makerCodes": {"PCCOOLER": 90587, "DEEPCOOL": 51853}},
        ],
    },
    "메인보드": {
        "categorySeq": 875,
        "categoryDepth": 2,
        "requests": [
            {"label": "MSI,ASUS,GIGABYTE", "makerCodes": {"MSI": 2904, "ASUS": 2869, "GIGABYTE": 3148}},
        ],
    },
    "RAM": {
        "categorySeq": 874,
        "categoryDepth": 2,
        "requests": [
            {"label": "삼성전자,TeamGroup", "makerCodes": {"삼성전자": 702, "TeamGroup": 4142}},
        ],
    },
    "그래픽카드": {
        "categorySeq": 876,
        "categoryDepth": 2,
        "requests": [
            {
                "label": "NVIDIA(칩셋)",
                # "칩셋 제조사 = NVIDIA" 필터. (제조사=NVIDIA 아님! 그건 워크스테이션 라인만 잡힘)
                "attributes": {"NVIDIA(칩셋)": "876|654|3518|S"},
            },
        ],
    },
    "SSD": {
        "categorySeq": 32617,
        "categoryDepth": 2,
        "requests": [
            {"label": "삼성전자", "makerCodes": {"삼성전자": 702}},
        ],
    },
    "HDD": {
        "categorySeq": 877,
        "categoryDepth": 2,
        "requests": [
            {"label": "Western Digital,Seagate", "makerCodes": {"Western Digital": 4213, "Seagate": 4202}},
        ],
    },
    "케이스": {
        "categorySeq": 879,
        "categoryDepth": 2,
        "requests": [
            {"label": "darkFlash,앱코", "makerCodes": {"darkFlash": 15938410, "앱코": 2108}},
        ],
    },
    "파워": {
        "categorySeq": 880,
        "categoryDepth": 2,
        "requests": [
            {"label": "마이크로닉스,darkFlash", "makerCodes": {"마이크로닉스": 3160, "darkFlash": 15938410}},
        ],
    },
}
