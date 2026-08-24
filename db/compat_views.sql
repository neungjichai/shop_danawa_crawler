-- ============================================================
-- 부품 호환성 매칭 뷰 (shop_danawa DB)
--
-- db/schema.sql의 호환성 컬럼(socket, form_factor, capacity_gb 등)을 이용해
-- 두 카테고리 사이의 "물리적으로 조립 가능한 조합"을 뷰로 만든다.
--
-- 표기 방식 차이 보정:
--   - CPU/메인보드의 socket 컬럼: "1851", "1700", "AM5" 처럼 순수 코드만 저장
--   - 쿨러의 support_sockets 컬럼: "LGA1700,LGA1851,AM4,AM5" 처럼 인텔에 LGA 접두사가 붙음
--   -> REGEXP '(^|,)(LGA)?소켓값(,|$)' 패턴으로 접두사 유무 상관없이 매칭한다.
--
-- 각 뷰는 최신가(products_v 뷰의 price_krw) 기준으로 만든다.
-- ============================================================

USE shop_danawa;

-- ------------------------------------------------------------
-- 1) CPU - 메인보드 : 소켓 매칭
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_cpu_mboard;
CREATE VIEW v_compat_cpu_mboard AS
SELECT
    c.product_id  AS cpu_id,
    c.name        AS cpu_name,
    c.socket      AS socket,
    c.price_krw   AS cpu_price,
    m.product_id  AS mboard_id,
    m.name        AS mboard_name,
    m.price_krw   AS mboard_price
FROM cpu_products_v c
JOIN mboard_products_v m
  ON m.socket = c.socket;

-- ------------------------------------------------------------
-- 2) 메인보드 - 케이스 : 폼팩터(ATX/M-ATX/M-ITX 등) 매칭
--    case_products.support_form_factors 는 "ATX,M-ATX,M-ITX" 형태의 콤마 목록이지만,
--    실제로는 "ATX(후면커넥터)"처럼 괄호가 붙거나, "ITX"(M- 접두사 없이)로 표기되는
--    경우가 있어 단순 완전일치로는 놓치는 조합이 생긴다. 아래 두 가지를 보정한다:
--      1) 괄호 및 괄호 안 내용 제거 후 비교 ("ATX(후면커넥터)" -> "ATX")
--      2) 메인보드가 M-ITX인 경우, 케이스가 "ITX"라고만 표기해도 호환으로 인정
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_mboard_case;
CREATE VIEW v_compat_mboard_case AS
SELECT
    m.product_id AS mboard_id,
    m.name       AS mboard_name,
    m.form_factor,
    m.price_krw  AS mboard_price,
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.price_krw  AS case_price
FROM mboard_products_v m
JOIN case_products_v ca
  ON (
        FIND_IN_SET(
            m.form_factor,
            REPLACE(REGEXP_REPLACE(ca.support_form_factors, '\\([^)]*\\)', ''), ' ', '')
        ) > 0
        OR (
            m.form_factor = 'M-ITX'
            AND FIND_IN_SET('ITX', REPLACE(REGEXP_REPLACE(ca.support_form_factors, '\\([^)]*\\)', ''), ' ', '')) > 0
        )
     )
WHERE m.form_factor IS NOT NULL
  AND ca.support_form_factors IS NOT NULL;

-- ------------------------------------------------------------
-- 3) 케이스 - 파워 : 파워 폼팩터(표준-ATX/SFX 등) 매칭
--    case_products.support_psu_form_factors 예: "표준-ATX", "M-ATX(SFX)"
--    power_products.form_factor 예: "ATX", "SFX", "TFX"
--
--    주의: "M-ATX(SFX)"처럼 케이스 외형과 실제 지원 파워규격이 같이 표기된 경우,
--    단순 LIKE '%ATX%' 매칭을 쓰면 "M-ATX"의 "ATX" 부분과 잘못 걸려서 SFX 전용
--    케이스인데 일반 ATX 파워까지 호환된다고 오판하게 된다(실제로는 물리적으로 안 들어감).
--    그래서 괄호가 있으면 괄호 안 값을 실제 규격으로, 없으면 "표준-" 접두사만 제거한
--    값을 실제 규격으로 보고 정확히 일치하는지로 비교한다.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_case_power;
CREATE VIEW v_compat_case_power AS
SELECT
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.support_psu_form_factors,
    p.product_id  AS power_id,
    p.name        AS power_name,
    p.form_factor AS power_form_factor,
    p.price_krw   AS power_price
FROM case_products_v ca
JOIN power_products_v p
  ON (
        CASE
            WHEN ca.support_psu_form_factors LIKE '%(%)%'
                THEN REGEXP_REPLACE(ca.support_psu_form_factors, '^.*\\(([^)]+)\\).*$', '\\1')
            ELSE REGEXP_REPLACE(ca.support_psu_form_factors, '^표준-', '')
        END
     ) = p.form_factor
WHERE ca.support_psu_form_factors IS NOT NULL
  AND p.form_factor IS NOT NULL;

-- ------------------------------------------------------------
-- 4) 케이스 - 쿨러 : 쿨러 높이가 케이스 최대 허용 높이 이내인지
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_case_cooler;
CREATE VIEW v_compat_case_cooler AS
SELECT
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.max_cooler_height_mm,
    co.product_id AS cooler_id,
    co.name       AS cooler_name,
    co.height_mm  AS cooler_height_mm,
    co.price_krw  AS cooler_price
FROM case_products_v ca
JOIN cooler_products_v co
  ON co.height_mm IS NOT NULL
 AND ca.max_cooler_height_mm IS NOT NULL
 AND co.height_mm <= ca.max_cooler_height_mm;

-- ------------------------------------------------------------
-- 5) 케이스 - 그래픽카드 : 그래픽카드 길이가 케이스 최대 허용 길이 이내인지
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_case_vga;
CREATE VIEW v_compat_case_vga AS
SELECT
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.max_vga_length_mm,
    v.product_id  AS vga_id,
    v.name        AS vga_name,
    v.length_mm   AS vga_length_mm,
    v.price_krw   AS vga_price
FROM case_products_v ca
JOIN vga_products_v v
  ON v.length_mm IS NOT NULL
 AND ca.max_vga_length_mm IS NOT NULL
 AND v.length_mm <= ca.max_vga_length_mm;

-- ------------------------------------------------------------
-- 6) 쿨러 - CPU : 소켓 지원 + TDP(발열) 감당 가능 여부
--    cooler_products.support_sockets 예: "LGA1700,LGA1851,AM4,AM5"
--    cpu_products.socket 예: "1851"(인텔, LGA 접두사 없음) / "AM5"(AMD, 그대로)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_cooler_cpu;
CREATE VIEW v_compat_cooler_cpu AS
SELECT
    co.product_id AS cooler_id,
    co.name       AS cooler_name,
    co.max_tdp_w,
    co.price_krw  AS cooler_price,
    c.product_id  AS cpu_id,
    c.name        AS cpu_name,
    c.power_max_w AS cpu_power_max_w,
    c.price_krw   AS cpu_price
FROM cooler_products_v co
JOIN cpu_products_v c
  ON co.support_sockets IS NOT NULL
 AND c.socket IS NOT NULL
 AND co.support_sockets REGEXP CONCAT('(^|,)(LGA)?', c.socket, '(,|$)')
 -- TDP 조건: 쿨러의 감당 가능 발열(max_tdp_w)이 CPU 최대 소비전력(power_max_w) 이상이어야 함.
 -- 둘 중 하나라도 값이 없으면(구형 CPU 등 파싱 실패) 소켓 매칭만으로 통과시킨다(보수적으로 later 확인 필요 표시).
 AND (co.max_tdp_w IS NULL OR c.power_max_w IS NULL OR co.max_tdp_w >= c.power_max_w);

-- ------------------------------------------------------------
-- 7) 메인보드 - RAM : DDR 규격(DDR4/DDR5) 매칭
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_mboard_ram;
CREATE VIEW v_compat_mboard_ram AS
SELECT
    m.product_id AS mboard_id,
    m.name       AS mboard_name,
    m.ram_type,
    m.ram_slot_count,
    m.price_krw  AS mboard_price,
    r.product_id AS ram_id,
    r.name       AS ram_name,
    r.capacity_gb,
    r.speed_mhz,
    r.price_krw  AS ram_price
FROM mboard_products_v m
JOIN ram_products_v r
  ON r.ram_type = m.ram_type
WHERE m.ram_type IS NOT NULL;

-- ------------------------------------------------------------
-- 8) 파워 용량 : 그래픽카드 권장 파워(recommended_psu_w) 충족 여부
--    (제조사가 이미 시스템 전체를 고려해 권장치를 주는 경우가 많아 이를 기준으로 삼는다.
--     더 보수적으로 보려면 안전마진을 추가로 둘 수 있다 — 아래 v_compat_power_capacity_safe 참고)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_power_vga;
CREATE VIEW v_compat_power_vga AS
SELECT
    p.product_id AS power_id,
    p.name       AS power_name,
    p.rated_w,
    p.price_krw  AS power_price,
    v.product_id AS vga_id,
    v.name       AS vga_name,
    v.recommended_psu_w,
    v.price_krw  AS vga_price
FROM power_products_v p
JOIN vga_products_v v
  ON v.recommended_psu_w IS NOT NULL
 AND p.rated_w >= v.recommended_psu_w;

-- 안전마진(10%)을 더 두고 싶을 때 쓰는 버전
DROP VIEW IF EXISTS v_compat_power_vga_safe;
CREATE VIEW v_compat_power_vga_safe AS
SELECT *
FROM v_compat_power_vga
WHERE rated_w >= recommended_psu_w * 1.1;

-- ------------------------------------------------------------
-- 9) 케이스 - 수랭쿨러 : 라디에이터 크기 매칭 (상세페이지 스펙 기반)
--    db/detail_spec_crawler.py로 수집한 case_products의 radiator_*_mm 컬럼 사용.
--    쿨러 쪽은 cooler_products.radiator_mm(목록 페이지 스펙에서 파싱, 수랭 쿨러만 존재)과 비교.
--    케이스가 상단/전면/후면/하단 중 어느 위치든 그 라디에이터 크기 이상을 지원하면 호환으로 본다.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_case_radiator;
CREATE VIEW v_compat_case_radiator AS
SELECT
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.radiator_top_mm, ca.radiator_front_mm, ca.radiator_rear_mm, ca.radiator_bottom_mm,
    co.product_id AS cooler_id,
    co.name       AS cooler_name,
    co.radiator_mm AS cooler_radiator_mm,
    co.price_krw  AS cooler_price
FROM case_products_v ca
JOIN cooler_products_v co
  ON co.cooler_type = 'liquid'
 AND co.radiator_mm IS NOT NULL
 AND (
        co.radiator_mm <= COALESCE(ca.radiator_top_mm, 0)
     OR co.radiator_mm <= COALESCE(ca.radiator_front_mm, 0)
     OR co.radiator_mm <= COALESCE(ca.radiator_rear_mm, 0)
     OR co.radiator_mm <= COALESCE(ca.radiator_bottom_mm, 0)
     );

-- ------------------------------------------------------------
-- 10) 케이스 - 파워 : PSU 길이 매칭 (기획서 "PSU 길이" 조건, 8개 결정론적 조건 중 하나)
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_compat_case_power_length;
CREATE VIEW v_compat_case_power_length AS
SELECT
    ca.product_id AS case_id,
    ca.name       AS case_name,
    ca.max_psu_length_mm,
    p.product_id  AS power_id,
    p.name        AS power_name,
    p.length_mm   AS power_length_mm,
    p.price_krw   AS power_price
FROM case_products_v ca
JOIN power_products_v p
  ON p.length_mm IS NOT NULL
 AND ca.max_psu_length_mm IS NOT NULL
 AND p.length_mm <= ca.max_psu_length_mm;

-- ------------------------------------------------------------
-- 11) 쿨러 - RAM : 방열판 간섭 참고용 (기획서 10번 조건)
--    "구조화된 치수 데이터로 확보되지 않는 항목"이라 기획서가 최종 필터링이 아닌
--    "참고 경고 문구"로만 쓰라고 명시했다 -- 그래서 이 뷰는 강제로 걸러내지 않고,
--    쿨러 높이와 RAM 방열판 높이를 나란히 보여주기만 한다. 실제 "간섭 여부"
--    판단(예: 공랭 쿨러 폭까지 고려한 물리적 간섭)은 Gemini 등 AI 모델의 보조
--    판단 몫으로 남겨둔다.
-- ------------------------------------------------------------
DROP VIEW IF EXISTS v_ram_cooler_clearance_reference;
CREATE VIEW v_ram_cooler_clearance_reference AS
SELECT
    co.product_id AS cooler_id,
    co.name       AS cooler_name,
    co.cooler_type,
    co.height_mm  AS cooler_height_mm,
    r.product_id  AS ram_id,
    r.name        AS ram_name,
    r.height_mm   AS ram_height_mm
FROM cooler_products_v co
JOIN ram_products_v r
  ON co.cooler_type = 'air'  -- 수랭은 라디에이터가 케이스에 붙으므로 RAM 간섭 이슈 없음
 AND r.height_mm IS NOT NULL;  -- 방열판 없는(height_mm NULL) RAM은 애초에 간섭 우려 없음
