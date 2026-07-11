# DATA_NOTES.md — 샘플 데이터 실측 명세

> 샘플 94쌍(`data/`, git 미추적) 전건 실측 결과. 전체 데이터 문서(데이터 설명서·활용 가이드라인)의 기준 서술과 다른 점을 우선 기록한다.
> 보안 규칙: 이 문서에는 스키마·규칙·집계 통계만 기록한다 (캡션 원문 전문 인용 금지, 이미지 포함 금지).

## 1. 구성

| 구분 | 수량 | 상세 |
|---|---|---|
| 풍력 | 75쌍 | 전부 2022년 Sungsan. 결함(PositiveDB) 74 + 정상(NormalDB) 1 |
| 태양광 | 19쌍 | 전부 2025년 (Eumseong 18, GyeonggiGwangju 1). 정상 16 + 결함 3 |

- 이미지 크기 실측: 풍력 8256×5504 RGB, 태양광 640×512 열화상.
- 디렉토리: `01.원천데이터`(JPG) / `02.라벨링데이터`(JSON), 하위 구조 동일 — `WindBlade/{A,B,C}/{LeadingEdge,PressureSide,SuctionSide,TrailingEdge}`, `SolarPanel/{Normal,Positive}/PanelFront`.
- **함정**: 풍력에는 Normal 폴더가 없고, 정상 1장(`2022_Sungsan_10_B_TrailingEdge_002`)이 결함 폴더에 섞여 있다. 정상/결함 판별은 폴더가 아니라 **`info.db_name`(NormalDB/PositiveDB) 기준**으로 할 것.

## 2. 파일명 규칙 (실측 — 문서 기준과 다름)

- 풍력: `연도_단지_호기_블레이드_부위_번호` 6토큰 (예: `2022_Sungsan_10_A_LeadingEdge_001`) — 문서와 일치.
- 태양광: `연도_단지_{Normal|Positive}_번호` **4토큰** (예: `2025_Eumseong_Normal_00001`) — 문서의 `panelFront` 토큰(5토큰)이 **실제로는 없음**. 파서는 4토큰 기준.

## 3. JSON 스키마 (실측)

최상위 키: `info`, `collection`, `categories`, `image`, `visionqa`(94/94), `annotations`(77/94 — 풍력 결함 74 + 태양광 결함 3. 정상 17건에는 키 자체가 없음).

- **QA 블록 키는 `visionqa`** — 문서의 `vision_qa`가 아님.
- 옵션은 평탄 필드(`_option_a`~`_option_d`)가 아니라 **중첩 dict**: `defect_classification_option: {"classification_option_a": ..., ...}`. 접두어가 문항마다 다름 (`detection_` / `localization_` / `analysis_` / `classification_`). 정답 필드(`*_a`)는 `"a"`~`"d"`.
- `annotations[].bbox`는 COCO `[x, y, w, h]` (실측 — 설명서 표의 xmin/ymax 기술은 오기).

### QA 3변형 (필드 구성이 3가지)

| 변형 | 건수 | 필드 |
|---|---|---|
| 정상 (풍력 정상 1 + 태양광 정상 16) | 17 | detection + object_description만 |
| 태양광 결함 | 3 | detection + localization (cropped_bbox **없음**) |
| 풍력 결함 | 74 | 4문항 전체 + cropped_bbox |

## 4. 정답 규칙 (전건 검증 완료)

- **대표결함** = 심각도 최고 → 동률 시 면적(area) 최대. 분류 문항 정답과 대조 **74/74 일치**.
- **풍력 localization 정답** = 대표결함 폴리곤을 `cropped_bbox` 창(원본 좌표계 [x,y,1920,1080])으로 **클리핑한 뒤의 타이트 bbox를 크롭 좌표계로 변환**한 값. **74/74 일치** (오차 ≤2px). annotations의 bbox 필드를 그대로 쓰면 창 밖 결함에서 틀린다 — 채점기·크롭 로직은 반드시 폴리곤 클리핑을 공유 구현으로 사용.
- **태양광 localization 정답** = 대표결함 bbox를 **원본 좌표계(640×512)** 에서 소수점 버림한 값. **3/3 일치**. (풍력과 좌표계가 다름 — cropped_bbox 없음)

## 5. 카테고리 매핑 (실측 — 설비별로 id 체계가 다름)

- 풍력: 1 Contamination / 2 Tape Damage / 3 Paint Damage / 4 La Exposure / 5 La Damage / 6 Bond Crack / 7 Receptor Damage / 8 Rain Collar / 9 Vortex Generator (문서 기준과 일치, 94건 내 일관).
- 태양광: **10 Hot Spot** 단일 (샘플 내 유일한 태양광 카테고리). 샘플에서는 풍력과 id 충돌 없음 — 단, 전체 데이터 적용 시 파싱 단계에서 id→name 일관성 전수 검증 필요.

## 6. 집계 통계 (풍력 결함 74건, 대표결함 기준)

- 클래스: Paint Damage 50 / Contamination 14 / La Exposure 5 / Bond Crack 2 / La Damage 1 / Rain Collar 1 / Receptor Damage 1 — **Tape Damage·Vortex Generator는 샘플에 없음** (UC-4 희귀 결함 시나리오는 모의로만 가능).
- 심각도: 1→14 / 2→52 / 3→5 / 4→3.
- 이미지당 결함 수: 1개 24건 ~ 최대 9개 1건 (복수 결함 50건 — 대표결함 선정 로직이 항상 필요).
- 홀드아웃 층화(U2) 참고: 클래스 7종 중 4종이 1~2건 → 층화 규칙은 U2 계획에서 확정.

## 7. 파서 구현 체크리스트 (함정 요약)

1. 정상/결함 판별은 `db_name` 기준 (폴더 아님 — §1 함정).
2. QA 키는 `visionqa`, 옵션은 문항별 접두어의 중첩 dict (§3).
3. `annotations` 부재(17건)를 정상 흐름으로 처리.
4. 좌표계 3종 구분: 풍력 annotations=원본(8256×5504) / 풍력 QA localization=1920×1080 크롭 / 태양광 QA localization=원본(640×512).
5. 태양광 파일명 4토큰 (부위 토큰 없음 → D1의 부위 컬럼은 `info.part_side_tag`에서).
6. 카테고리 매핑은 파일별 `categories` 블록에서 읽고 전수 일관성 검증.
