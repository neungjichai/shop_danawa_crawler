# -*- coding: utf-8 -*-
"""
크롤러가 수집한 spec(목록 페이지 스펙 요약 텍스트)과 name(상품명)에서
db/schema.sql의 호환성 컬럼 값을 파싱해서 뽑아낸다.

주의: 다나와 "상세페이지"를 따로 긁는 게 아니라 "목록 페이지"의 요약 스펙
한 줄에서 정규식으로 뽑는 방식이라, 일부 필드는 표기가 없는 상품의 경우
None(=DB에서는 NULL)이 된다. 이건 정상이며, 나중에 상세페이지 스펙 크롤러를
추가하면 채울 수 있다.
"""

import re


def _search(pattern: str, text: str, group: int = 1):
    m = re.search(pattern, text)
    return m.group(group) if m else None


def _to_int(s):
    if s is None:
        return None
    s = s.replace(",", "")
    try:
        return int(float(s))
    except ValueError:
        return None


def parse_capacity_gb_from_name(name: str):
    """
    상품명의 용량 표기를 GB 단위로 변환.
    예: "(2TB)" -> 2000, "(512GB)" -> 512, "(2TB, ST2000DM001)" -> 2000 (모델코드 동반),
        "(4x18TB)" -> 18000 (여러 개 묶음 판매 시 개별 드라이브 용량 기준 — 묶음 개수는 무시),
        "(32GB(16Gx2))" -> 32 (총 용량. 뒤의 "16Gx2"는 스틱당 용량x개수라 무시)
    괄호 바로 뒤에 TB/GB가 오는 첫 번째 지점을 총 용량으로 본다 (뒤에 어떤 문자가 오든 상관없음).
    """
    m = re.search(r"\((?:\d+\s*[xX]\s*)?(\d+(?:\.\d+)?)\s*(TB|GB)", name, re.IGNORECASE)
    if not m:
        return None
    value, unit = float(m.group(1)), m.group(2).upper()
    return int(value * 1000) if unit == "TB" else int(value)


def is_multi_pack(name: str) -> bool:
    """상품명에 'N x 용량' 형태의 다중 묶음(벌크/기업용) 표기가 있는지 확인."""
    return bool(re.search(r"\(\d+\s*[xX]\s*\d+(?:\.\d+)?\s*(TB|GB)\)", name, re.IGNORECASE))


# ---------------- CPU ----------------
def parse_cpu(name: str, spec: str) -> dict:
    socket = _search(r"소켓(\w+)", spec)

    # 내장그래픽 유무: UHD/HD/Xe 그래픽스 등 실제 모델명이 보이면 Y, "미탑재"만 있으면 N
    # (AMD는 모델명 없이 "탑재"/"미탑재"만 표기하는 경우가 있어 별도로 처리)
    if re.search(r"UHD\s*\d|HD\s*[A-Z0-9]|인텔 HD(?!\w)|Xe\s*그래픽스|인텔 그래픽스|아이리스|Iris|Radeon", spec):
        has_igpu = "Y"
    elif "미탑재" in spec:
        has_igpu = "N"
    elif re.search(r"(?<!미)탑재", spec):  # "미탑재"가 아닌 "탑재"만 단독으로 있는 경우 (AMD 표기 방식)
        has_igpu = "Y"
    else:
        has_igpu = None

    # 전력: 최신 인텔은 "PBP-MTP:125-250W", 구세대 인텔은 "TDP:65~117W"/"TDP:65W",
    # AMD는 "TDP:65W/PPT:88W" 형태로 TDP(기본)와 PPT(실제 최대 소비전력)를 따로 표기한다
    # (PPT가 인텔의 MTP/최대값에 해당하는 개념이라 min=TDP, max=PPT로 매핑).
    # 단위(W)가 생략된 경우도 있어(예: "TDP: 65 / PPT: 88") W를 선택적으로 처리한다.
    pmin = pmax = None
    m = re.search(r"PBP-MTP:(\d+)-(\d+)W", spec)
    if m:
        pmin, pmax = int(m.group(1)), int(m.group(2))
    else:
        m = re.search(r"TDP:\s*(\d+)W?.*?PPT:\s*(\d+)W?", spec)  # AMD
        if m:
            pmin, pmax = int(m.group(1)), int(m.group(2))
        else:
            m = re.search(r"TDP:\s*(\d+)(?:~(\d+))?W?", spec)  # 구세대 인텔
            if m:
                pmin = int(m.group(1))
                pmax = int(m.group(2)) if m.group(2) else pmin

    return {"socket": socket, "has_igpu": has_igpu, "power_min_w": pmin, "power_max_w": pmax}


# ---------------- VGA(그래픽카드) ----------------
def parse_vga(name: str, spec: str) -> dict:
    length_mm = _to_int(_search(r"가로\(길이\):(\d+(?:\.\d+)?)mm", spec))
    recommended_psu_w = _to_int(_search(r"(\d+)W\s*이상", spec))
    power_connector = _search(r"전원 포트:([^/]+)", spec)
    return {
        "length_mm": length_mm,
        "recommended_psu_w": recommended_psu_w,
        "power_connector": power_connector,
    }


# ---------------- 메인보드 ----------------
def parse_mboard(name: str, spec: str) -> dict:
    socket = _search(r"소켓(\w+)", spec)
    ram_type = _search(r"(DDR\d)", spec)
    form_factor = _search(r"/(ATX|M-ATX|M-ITX|E-ATX)\s*\(", spec)
    # "8200MHz (PC5-65600)/4개/메모리 용량" 패턴에서 슬롯 개수 추출
    ram_slot_count = _to_int(_search(r"MHz\s*\(PC\d-\d+\)/(\d+)개", spec))
    sata_ports = _to_int(_search(r"SATA3:(\d+)개", spec))
    return {
        "socket": socket,
        "ram_type": ram_type,
        "form_factor": form_factor,
        "ram_slot_count": ram_slot_count,
        "sata_ports": sata_ports,
    }


# ---------------- RAM ----------------
def parse_ram(name: str, spec: str) -> dict:
    ram_type = _search(r"(DDR\d)", spec)
    speed_mhz = _to_int(_search(r"(\d+)MHz", spec))
    capacity_gb = parse_capacity_gb_from_name(name)
    # 방열판 높이 (기획서 "10번 조건: 쿨러↔RAM 간섭" 판단에 필요). 방열판 없는 RAM은 이 필드 자체가 없어 NULL이 정상.
    height_mm = _to_int(_search(r"높이:(\d+(?:\.\d+)?)mm", spec))
    return {"ram_type": ram_type, "speed_mhz": speed_mhz, "capacity_gb": capacity_gb, "height_mm": height_mm}


# ---------------- SSD ----------------
def parse_ssd(name: str, spec: str) -> dict:
    capacity_gb = parse_capacity_gb_from_name(name)
    if "NVMe" in spec or "PCIe" in spec:
        interface = "M.2 NVMe" if "M.2" in spec else "PCIe"
    elif "SATA" in spec:
        interface = "SATA" if "M.2" not in spec else "M.2 SATA"
    else:
        interface = None

    # PCIe 버전: "PCIe4.0x4", "PCIe5.0x4" 형태. 여러 버전이 같이 표기되면(듀얼모드) 더 높은 버전을 채택.
    pcie_versions = re.findall(r"PCIe(\d(?:\.\d)?)x\d", spec)
    pcie_version = max(pcie_versions, key=float) if pcie_versions else None

    return {"capacity_gb": capacity_gb, "interface": interface, "pcie_version": pcie_version}


# ---------------- HDD ----------------
def parse_hdd(name: str, spec: str) -> dict:
    capacity_gb = parse_capacity_gb_from_name(name)
    return {"capacity_gb": capacity_gb, "is_multi_pack": is_multi_pack(name)}


# ---------------- 쿨러 ----------------
def parse_cooler(name: str, spec: str) -> dict:
    intel_sockets = _search(r"인텔 소켓:([^/]+)", spec)
    amd_sockets = _search(r"AMD 소켓:([^/]+)", spec)
    sockets = [s for s in [intel_sockets, amd_sockets] if s]
    support_sockets = ",".join(sockets) if sockets else None

    height_mm = _to_int(_search(r"높이:(\d+(?:\.\d+)?)mm", spec))
    max_tdp_w = _to_int(_search(r"TDP:(\d+)W", spec))

    if "수랭" in spec or "라디에이터" in spec:
        cooler_type = "liquid"
    elif "공랭" in spec:
        cooler_type = "air"
    else:
        cooler_type = None

    radiator_mm = _to_int(_search(r"라디에이터\D{0,10}(\d+)mm", spec))

    return {
        "support_sockets": support_sockets,
        "height_mm": height_mm,
        "cooler_type": cooler_type,
        "radiator_mm": radiator_mm,
        "max_tdp_w": max_tdp_w,
    }


# ---------------- 파워(PSU) ----------------
def parse_power(name: str, spec: str) -> dict:
    rated_w = _to_int(_search(r"/(\d+)W/", spec))
    # "M-ATX(SFX) 파워"처럼 실제 규격이 괄호 안에 따로 표기되는 경우를 우선 확인
    form_factor = _search(r"^[\w-]+\((\w+(?:-L)?)\)\s*파워", spec)
    if not form_factor:
        form_factor = _search(r"^(ATX|SFX|SFX-L|TFX)\s*파워", spec)

    # 인증등급: "80 PLUS" 표기가 있으면 그걸 우선, 없으면 "ETA인증" 표기를 대신 사용.
    # 둘 다 없으면 인증 자체가 없는(저가형) 제품일 수 있음 -> NULL
    certification = _search(r"80 PLUS ([^/]+)", spec)
    if not certification:
        eta = _search(r"ETA인증:([^/]+)", spec)
        certification = f"ETA-{eta}" if eta else None

    length_mm = _to_int(_search(r"깊이:(\d+)mm", spec))  # ★ 추가: PSU 자체 길이 (기획서 "PSU 길이" 조건)

    return {
        "rated_w": rated_w,
        "form_factor": form_factor,
        "certification": certification,
        "length_mm": length_mm,
    }


# ---------------- 케이스 ----------------
def parse_case(name: str, spec: str) -> dict:
    support_form_factors = _search(r"지원보드규격:([^/]+)", spec)
    max_cooler_height_mm = _to_int(_search(r"CPU쿨러 높이:(\d+(?:\.\d+)?)mm", spec))
    max_vga_length_mm = _to_int(_search(r"VGA 길이:(\d+(?:\.\d+)?)mm", spec))
    support_psu_form_factors = _search(r"지원파워규격:([^/]+)", spec)
    max_psu_length_mm = _to_int(_search(r"파워 장착 길이:(\d+(?:\.\d+)?)mm", spec))  # ★ 추가: 기획서 "PSU 길이" 조건
    return {
        "support_form_factors": support_form_factors,
        "max_cooler_height_mm": max_cooler_height_mm,
        "max_vga_length_mm": max_vga_length_mm,
        "support_psu_form_factors": support_psu_form_factors,
        "max_psu_length_mm": max_psu_length_mm,
    }


PARSERS = {
    "CPU": parse_cpu,
    "그래픽카드": parse_vga,
    "메인보드": parse_mboard,
    "RAM": parse_ram,
    "SSD": parse_ssd,
    "HDD": parse_hdd,
    "쿨러": parse_cooler,
    "파워": parse_power,
    "케이스": parse_case,
}
