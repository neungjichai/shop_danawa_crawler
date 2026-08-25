# -*- coding: utf-8 -*-
"""
CPU / 그래픽카드 성능 등급 (기획서 v4.0 "6. 부품 성능 등급 기준" 반영).

이 모듈은 두 가지를 따로 제공한다:

1) rank_score(name) -> 정수 점수 (일반 등급, 전체 상품 대상)
   - 기획서의 "원칙"(체급/라인업 우선, 세대·접미사는 보정)을 연속적인 점수로 계산.
   - 오래된 세대(2세대 샌디브릿지, GTX10 시리즈 등 기획서 표에 없는 것)까지 포함해서
     전체 크롤링 데이터에 순위를 매길 수 있다.
   - 한계: 기획서가 예로 든 "i5-14600K ≈ i7-13700", "5060 Ti가 4070에 턱밑 추격"
     같은 미세한 교차 비교까지 정확히 재현하지는 못한다 (체급 차이를 전반적으로
     지키면서 특정 케이스만 역전시키는 건 하나의 수식으로 동시에 만족 불가능).
     이런 정밀 비교가 필요하면 아래 2)를 쓴다.

2) upgrade_candidates(name) -> 기획서 6장에 나온 "정확한 모델명 순서표" 조회.
   - "한 단계 위/아래" 업그레이드 추천(기능4)처럼 기획서가 예로 든 것과
     정확히 일치해야 하는 기능에 사용.
   - 13/14세대 + 코어 울트라, RTX 30~50 시리즈만 커버한다 (기획서 표 범위 그대로).
     이 범위 밖의(예: 스카이레이크, GTX10 시리즈) 오래된 부품은 이 표에 없다 —
     그런 구형 부품의 "한 단계 업그레이드"가 필요하면 rank_score로 대체 판단해야 한다.
"""

import re

# ============================================================
# 1) 일반 등급 점수 (rank_score) — 전체 상품 대상
# ============================================================

# ---------------- CPU ----------------
# 세대별 상대적 신구 순서 (숫자가 클수록 신형). 인텔 공식 세대 번호와 반드시 일치하진
# 않지만("코어 울트라"는 세대번호가 없음), 출시 순서를 그대로 반영한 값이다.
CPU_GEN_ORDER = {
    "1": 1,      # 린필드
    "2": 2,      # 샌디브릿지
    "3": 3,      # 아이비브릿지
    "4": 4,      # 하스웰 / 하스웰 리프레시(같은 4로 취급, 세부 구분 안 함)
    "6": 6,      # 스카이레이크
    "7": 7,      # 카비레이크
    "8": 8,      # 커피레이크
    "9": 9,      # 커피레이크-R
    "10": 10,    # 코멧레이크
    "11": 11,    # 로켓레이크
    "12": 12,    # 엘더레이크
    "13": 13,    # 랩터레이크
    "14": 14,    # 랩터레이크 리프레시
}
CPU_ULTRA_GEN = 15  # 코어 울트라(시리즈1/2 구분 안 함) - 14세대보다 신형으로 취급

# AMD 라이젠 세대(-N세대 표기) -> 인텔과 같은 "출시 시기 축(recency scale)"으로 환산.
# 주의: 인텔/AMD 둘 다 "-N세대"라고 표기하지만 실제 출시 시기는 완전히 다르다
# (예: 인텔 6세대=2015년 스카이레이크, 라이젠 6세대=2024년 Zen5). 절대 같은 숫자를
# 그대로 비교하면 안 되고, 아래처럼 각자 축을 나눠서 인텔 세대 스케일에 맞춰 변환한다.
# (대략적인 출시 시기 매칭이며 정밀한 벤치마크 비교는 아니다)
AMD_GEN_TO_INTEL_SCALE = {
    "3": 9,    # 라이젠 3세대(Zen2, 2019) ≈ 인텔 9~10세대 시기
    "4": 11,   # 라이젠 4세대(Zen3, 2020) ≈ 인텔 11세대 시기
    "5": 13,   # 라이젠 5세대(Zen4, 2022) ≈ 인텔 12~13세대 시기
    "6": 15,   # 라이젠 6세대(Zen5, 2024) ≈ 인텔 14세대~코어울트라 시기
}

CPU_LINEUP_SCORE = {
    "셀러론": 0,
    "펜티엄": 1,
    "코어i3": 2,
    "라이젠3": 2,  # 인텔 i3와 동급 라인업으로 취급
    "코어 울트라5": 3,  # i5와 동급 라인업으로 취급 (기획서 6.2 표: i5 계열 시퀀스 안에 울트라5가 껴 있음)
    "코어i5": 3,
    "라이젠5": 3,
    "코어 울트라7": 4,
    "코어i7": 4,
    "라이젠7": 4,
    "코어 울트라9": 5,
    "코어i9": 5,
    "라이젠9": 5,
    "제온": 5,  # 서버용, 보통 exclude_rules에서 걸러지지만 방어적으로 i9와 동급 취급
    "코어X-시리즈": 6,  # HEDT급(i9-X 등) - 일반 i9보다 위 (기획서 표엔 없음, 자체 판단)
}


def _cpu_lineup(name: str):
    # 더 구체적인(울트라) 패턴을 먼저 검사해야 "코어i5"에 오검색되지 않는다.
    for key in ["코어X-시리즈", "코어 울트라5", "코어 울트라7", "코어 울트라9", "셀러론", "펜티엄",
                "코어i3", "코어i5", "코어i7", "코어i9", "제온",
                "라이젠3", "라이젠5", "라이젠7", "라이젠9"]:
        if key in name:
            return key
    return None


# 코드네임 -> 세대 매핑 (셀러론/펜티엄처럼 "-N세대" 표기가 없고 코드네임만 있는 경우 대비)
CPU_CODENAME_GEN = {
    "하스웰 리프레시": 4, "하스웰": 4,
    "스카이레이크": 6, "카비레이크": 7,
    "커피레이크-R": 9, "커피레이크": 8,
    "코멧레이크S": 10, "코멧레이크": 10,
    "로켓레이크S": 11,
    "엘더레이크": 12,
    "랩터레이크 리프레시": 14, "랩터레이크": 13,
    "애로우레이크 리프레시": CPU_ULTRA_GEN, "애로우레이크": CPU_ULTRA_GEN,
    "캐스케이드레이크": 9,  # 코어X-시리즈(HEDT)용
}


def _cpu_gen(name: str):
    m = re.search(r"-(\d+)세대", name)
    if m:
        gen_num = m.group(1)
        is_amd = "라이젠" in name or "AMD" in name
        if is_amd:
            if gen_num in AMD_GEN_TO_INTEL_SCALE:
                return AMD_GEN_TO_INTEL_SCALE[gen_num]
        elif gen_num in CPU_GEN_ORDER:
            return CPU_GEN_ORDER[gen_num]
    if "울트라" in name:
        return CPU_ULTRA_GEN
    for codename, gen in CPU_CODENAME_GEN.items():
        if codename in name:
            return gen
    return None


def cpu_rank_score(name: str):
    lineup = _cpu_lineup(name)
    gen = _cpu_gen(name)
    if lineup is None or gen is None:
        return None

    lineup_score = CPU_LINEUP_SCORE[lineup]
    is_amd = "라이젠" in name or "AMD" in name

    if is_amd:
        # AMD: X3D(3D V-Cache, 게이밍 실성능 크게 우위) > X(오버클럭 가능) > 기본형
        if "X3D" in name:
            suffix_bonus = 3
        elif re.search(r"\dX(?!\w)", name):
            suffix_bonus = 1
        else:
            suffix_bonus = 0
    else:
        # 인텔: K/KF(배수제한 해제) 우대. F(내장그래픽 미탑재)는 연산 성능에 영향 없어 보정 없음 (기획서 6.2)
        suffix_bonus = 1 if re.search(r"\d(K|KF)(?!\w)", name) else 0

    # 라인업이 압도적 1순위, 세대가 2순위, 접미사가 미세 보정.
    # (기획서의 "i5-14600K ≈ i7-13700" 같은 교차 사례는 이 공식으로 정확히
    #  재현되지 않는다 - 모듈 docstring 참고, 필요하면 upgrade_candidates() 사용)
    return lineup_score * 1000 + gen * 10 + suffix_bonus


# ---------------- 그래픽카드 (NVIDIA) ----------------
# 체급(뒤 숫자) 우선 원칙 (기획서 6.1) -> class_score를 압도적 1순위로 둔다.
GPU_CLASS_SCORE = {
    # 구형(기획서 표 밖) 폴백용
    "210": 1,  # G210 (초저가형, GT710/730보다도 구형)
    "710": 1, "730": 1, "1030": 1,
    "1050": 2, "1650": 3, "1660": 3,
    "2060": 4,
    # 기획서 6.1 표 범위 (30~50 시리즈)
    "3050": 5, "3060": 6, "3070": 7, "3080": 8, "3090": 9,
    "4060": 6, "4070": 7, "4080": 8, "4090": 9,
    "5050": 5, "5060": 6, "5070": 7, "5080": 8, "5090": 9,
}
GPU_GEN_SCORE = {"GTX10": 1, "GTX16": 2, "RTX20": 3, "RTX30": 4, "RTX40": 5, "RTX50": 6}


def _gpu_model_num(name: str):
    m = re.search(r"(?:GTX|RTX|GT|G)\s*(\d{3,4})", name)
    return m.group(1) if m else None


def _gpu_gen(model_num: str, name: str):
    if "RTX" in name:
        prefix = model_num[0]  # "5070" -> "5"
        return GPU_GEN_SCORE.get(f"RTX{prefix}0", None)
    if "GTX" in name:
        if model_num.startswith("16"):
            return GPU_GEN_SCORE["GTX16"]
        return GPU_GEN_SCORE["GTX10"]
    return 0  # GT 710/730/1030 등 초저가형


def gpu_rank_score(name: str):
    model_num = _gpu_model_num(name)
    if model_num is None or model_num not in GPU_CLASS_SCORE:
        return None

    class_score = GPU_CLASS_SCORE[model_num]
    gen_score = _gpu_gen(model_num, name) or 0

    # 접미사: Ti > SUPER > 기본형 (기획서 6.1). 체급을 완전히 뒤집진 못하지만
    # "턱밑 추격"이 가능할 정도의 보정치를 준다.
    if re.search(r"\bTi\b", name):
        suffix_bonus = 3
    elif "SUPER" in name.upper():
        suffix_bonus = 2
    else:
        suffix_bonus = 0

    # 체급이 압도적 1순위, 세대가 2순위(동일 체급 내 신형 우대), 접미사가 미세 보정.
    return class_score * 1000 + gen_score * 10 + suffix_bonus


# 기존 코드 호환용 별칭 (예전엔 1~5 등급이었지만, 이제 연속 점수를 반환한다)
cpu_tier = cpu_rank_score
gpu_tier = gpu_rank_score


# ============================================================
# 2) 정확한 업그레이드 순서표 (기획서 6장 표 그대로) — 기능4용
# ============================================================

# 각 시퀀스는 "낮음 -> 높음" 순서. 기획서 6.2절 표 그대로 옮김.
CPU_UPGRADE_SEQUENCES = {
    "i3": ["13100", "14100"],
    "i5": ["13400", "14400", "13500", "14500", "코어 울트라5 245K", "13600K", "14600K"],
    "i7": ["13700", "코어 울트라7 265K", "14700", "13700K", "14700K"],
    "i9": ["13900", "코어 울트라9 285K", "14900", "13900K", "14900K", "14900KS"],
}

# 기획서 6.1절 표 그대로. 구간(엔트리/하이엔드/플래그십)별로 낮음->높음 순서.
GPU_UPGRADE_SEQUENCES = {
    "60계열": ["4060", "5060", "4060 Ti", "5060 Ti"],
    "70계열": ["4070", "4070 SUPER", "5070", "4070 Ti", "5070 Ti"],
    "80/90계열": ["4080", "4080 SUPER", "5080", "4090", "5090"],
}


def _find_in_sequence(name: str, sequences: dict):
    """
    상품명이 어느 시퀀스의 몇 번째 위치에 있는지 찾는다. 못 찾으면 None.
    "5060"과 "5060 Ti"처럼 한쪽이 다른 쪽의 부분 문자열인 토큰이 섞여있을 수 있으므로,
    후보를 전부 모은 뒤 "가장 구체적인(부분 개수가 많은) 토큰"을 우선 채택한다.
    """
    best = None  # (matched_parts_count, seq_name, idx, items)
    normalized_name = name.replace("-", "")

    for seq_name, items in sequences.items():
        for idx, token in enumerate(items):
            parts = token.split()
            if all(p in normalized_name for p in parts):
                candidate = (len(parts), seq_name, idx, items)
                if best is None or candidate[0] > best[0]:
                    best = candidate

    if best is None:
        return None
    _, seq_name, idx, items = best
    return seq_name, idx, items


def upgrade_candidates(name: str, category: str):
    """
    기획서 표 기준으로 이 상품의 "한 단계 위" / "한 단계 아래" 후보를 알려준다.
    category: "CPU" 또는 "그래픽카드"
    반환: {"sequence": 시퀀스이름, "position": 몇번째(0부터), "lower": 아래 모델 or None, "upper": 위 모델 or None}
          기획서 표 범위 밖(구형 부품 등)이면 None
    """
    sequences = CPU_UPGRADE_SEQUENCES if category == "CPU" else GPU_UPGRADE_SEQUENCES
    found = _find_in_sequence(name, sequences)
    if not found:
        return None

    seq_name, idx, items = found
    return {
        "sequence": seq_name,
        "position": idx,
        "lower": items[idx - 1] if idx > 0 else None,
        "upper": items[idx + 1] if idx < len(items) - 1 else None,
    }


if __name__ == "__main__":
    print("=== 일반 등급 점수 (rank_score) ===")
    cpu_tests = [
        "인텔 셀러론 G5905 (코멧레이크S) (벌크)",
        "인텔 코어i5-2세대 2500 (샌디브릿지) (벌크)",
        "인텔 코어i5-14세대 14400F (랩터레이크 리프레시) (벌크)",
        "인텔 코어i7-13세대 13700K (랩터레이크) (벌크)",
        "인텔 코어 울트라9 시리즈2 285K (애로우레이크) (정품)",
    ]
    for t in cpu_tests:
        print(f"{t} -> {cpu_rank_score(t)}")

    print()
    gpu_tests = [
        "MSI 지포스 GT710 D3 2GB LP 무소음",
        "PALIT 지포스 GTX 1050 Ti D5 4GB",
        "PALIT 지포스 RTX 4070 D6X 12GB",
        "PALIT 지포스 RTX 5060 Ti DUAL D7 8GB",
        "MSI 지포스 RTX 5090 D7 32GB",
    ]
    for t in gpu_tests:
        print(f"{t} -> {gpu_rank_score(t)}")

    print()
    print("=== 정확한 업그레이드 순서 (기획서 6장 표) ===")
    upgrade_tests_cpu = [
        "인텔 코어i5-14세대 14400F (랩터레이크 리프레시) (벌크)",
        "인텔 코어i5-13세대 13600K (랩터레이크) (벌크)",
        "인텔 코어i7-13세대 13700 (랩터레이크) (벌크)",
    ]
    for t in upgrade_tests_cpu:
        print(f"{t} -> {upgrade_candidates(t, 'CPU')}")

    upgrade_tests_gpu = [
        "PALIT 지포스 RTX 5060 Ti DUAL D7 8GB",
        "MSI 지포스 RTX 4070 게이밍 트리오 D6X 12GB",
    ]
    for t in upgrade_tests_gpu:
        print(f"{t} -> {upgrade_candidates(t, '그래픽카드')}")
