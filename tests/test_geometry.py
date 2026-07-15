"""localization 정답 좌표 계산 테스트 — 채점기·T4가 공유하는 단일 구현 (ADR-0005).

풍력: 대표결함 폴리곤 → 크롭 창 클리핑 → 타이트 bbox → 크롭 좌표계 변환.
태양광: 대표결함 bbox 소수점 버림 (원본 좌표계).
"""

import json

import pytest

from defect_agent.geometry import GeometryError, localization_bbox
from defect_agent.labels import parse_label_file

크롭_창 = [2801, 2549, 1920, 1080]  # 원본 좌표계 [x, y, 1920, 1080]

풍력_카테고리 = [{"id": 5, "name": "La Damage", "supercategory": "풍력 내부"}]
풍력_결함_경로 = "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json"


def _문항(종류: str, 보기: dict[str, str], 정답: str) -> dict:
    return {
        f"defect_{종류}_q": f"{종류} 질문",
        f"defect_{종류}_option": {f"{종류}_option_{k}": v for k, v in 보기.items()},
        f"defect_{종류}_a": 정답,
    }


def 풍력_결함_데이터(polygon: list[float]) -> dict:
    """풍력 결함 변형 — 대표결함 폴리곤만 바꿔가며 기하를 검증한다."""
    xs, ys = polygon[0::2], polygon[1::2]
    bbox = [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]
    visionqa = {"object_description": "블레이드 표면 설명"}
    visionqa |= _문항("detection", {"a": "예", "b": "아니오"}, "a")
    visionqa |= _문항(
        "localization",
        {"a": "[1,2,3,4]", "b": "[5,6,7,8]", "c": "[9,10,11,12]", "d": "[13,14,15,16]"},
        "b",
    )
    visionqa |= _문항("analysis", {"a": "원인1", "b": "원인2", "c": "원인3", "d": "원인4"}, "c")
    visionqa |= _문항(
        "classification",
        {"a": "La Damage", "b": "Paint Damage", "c": "Contamination", "d": "Hot Spot"},
        "a",
    )
    visionqa["cropped_bbox"] = list(크롭_창)
    return {
        "info": {
            "db_name": "PositiveDB",
            "generator_name": "풍력",
            "part_side_tag": "Leading Edge",
        },
        "collection": {"location": "Sungsan", "datetime": "2022-04-06 16:15:23"},
        "categories": 풍력_카테고리,
        "image": {
            "id": 1,
            "width": 8256,
            "height": 5504,
            "filename": "2022_Sungsan_10_A_LeadingEdge_001.jpg",
        },
        "annotations": [
            {
                "id": 1001,
                "image_id": 1,
                "category_id": 5,
                "segmentation": polygon,
                "area": 100.0,
                "bbox": bbox,
                "severity": 4,
            }
        ],
        "visionqa": visionqa,
    }


def _레코드(tmp_path, 상대경로: str, 데이터: dict):
    경로 = tmp_path / 상대경로
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(json.dumps(데이터, ensure_ascii=False), encoding="utf-8")
    return parse_label_file(경로)


# ── 테스트 4: 창 완전 내부 폴리곤 ──


def test_창_내부_폴리곤은_평행이동한_타이트_bbox(tmp_path):
    # 폴리곤 사각형 (3000,2800)~(3100,2850) — 창(x 2801~4721, y 2549~3629) 완전 내부
    polygon = [3000.0, 2800.0, 3100.0, 2800.0, 3100.0, 2850.0, 3000.0, 2850.0]
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터(polygon))

    # 크롭 좌표계: x = 3000-2801 = 199, y = 2800-2549 = 251
    assert localization_bbox(record) == (199, 251, 100, 50)


# ── 테스트 5: 창 경계에 걸친 폴리곤 — 클리핑 없이는 조용히 틀리는 경로 ──


def test_창_경계에_걸친_폴리곤은_클리핑_후_타이트_bbox(tmp_path):
    # 창 오른쪽 경계 x=4721을 넘는 사각형 (4600,2600)~(4900,2700)
    polygon = [4600.0, 2600.0, 4900.0, 2600.0, 4900.0, 2700.0, 4600.0, 2700.0]
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터(polygon))

    # 클리핑: x는 4721에서 잘림 → 크롭 좌표 (1799, 51), 폭 4721-4600=121
    assert localization_bbox(record) == (1799, 51, 121, 100)


# ── 테스트 6: 꼭짓점이 창 경계 위에 정확히 놓임 ──


def test_창_경계_위_꼭짓점은_내부로_유지(tmp_path):
    # 왼쪽 변 두 꼭짓점이 창 왼쪽 경계 x=2801 위에 정확히 놓인 사각형
    polygon = [2801.0, 2600.0, 2900.0, 2600.0, 2900.0, 2700.0, 2801.0, 2700.0]
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터(polygon))

    # 경계 위 점이 잘려나가면 안 됨 — x=0부터 시작해야 한다
    assert localization_bbox(record) == (0, 51, 99, 100)


# ── 테스트 7: 태양광은 원본 좌표계 bbox 소수점 버림 ──


def 태양광_결함_데이터() -> dict:
    """태양광 결함 변형 — detection + localization, cropped_bbox 없음, 좌표계는 원본."""
    visionqa = {"object_description": "패널 열화상 설명"}
    visionqa |= _문항("detection", {"a": "예", "b": "아니오"}, "a")
    visionqa |= _문항(
        "localization",
        {"a": "[191,65,7,6]", "b": "[0,0,10,10]", "c": "[100,100,5,5]", "d": "[300,300,8,8]"},
        "a",
    )
    return {
        "info": {"db_name": "PositiveDB", "generator_name": "태양광", "part_side_tag": "Front"},
        "collection": {"location": "Eumseong", "datetime": "2025-05-01 11:00:00"},
        "categories": [{"id": 10, "name": "Hot Spot", "supercategory": "태양광 온도"}],
        "image": {
            "id": 118506,
            "width": 640,
            "height": 512,
            "filename": "2025_Eumseong_Positive_00001.jpg",
        },
        "annotations": [
            {
                "id": 118506001,
                "image_id": 118506,
                "category_id": 10,
                "segmentation": [191.41, 65.83, 199.21, 65.83, 199.21, 71.83],
                "area": 37.0,
                "bbox": [191.41, 65.83, 7.8, 6.0],
                "severity": 3,
            }
        ],
        "visionqa": visionqa,
    }


태양광_결함_경로 = "SolarPanel/Positive/PanelFront/2025_Eumseong_Positive_00001.json"


def test_태양광은_bbox_소수점_버림(tmp_path):
    record = _레코드(tmp_path, 태양광_결함_경로, 태양광_결함_데이터())

    # [191.41, 65.83, 7.8, 6.0] → 버림 (191, 65, 7, 6) — 크롭 변환 없음
    assert localization_bbox(record) == (191, 65, 7, 6)


# ── 테스트 13: 폴리곤이 창과 겹치지 않음 — 데이터상 없어야 할 상황, fail-fast (계획서 D4) ──


def test_창과_겹치지_않는_폴리곤은_에러(tmp_path):
    # 창 [2801,2549,1920,1080]에서 완전히 벗어난 사각형 (100,100)~(200,200)
    polygon = [100.0, 100.0, 200.0, 100.0, 200.0, 200.0, 100.0, 200.0]
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터(polygon))

    with pytest.raises(GeometryError, match="겹치지 않음"):
        localization_bbox(record)


def test_창에_접촉만_하는_폴리곤은_에러(tmp_path):
    """면적 0 접촉은 공집합 검사를 우회해 (x,y,0,0)이 되던 경로 (적대적 리뷰 M2)."""
    # 오른쪽 변이 창 왼쪽 경계 x=2801에 닿기만 하는 사각형 (2700,2600)~(2801,2700)
    polygon = [2700.0, 2600.0, 2801.0, 2600.0, 2801.0, 2700.0, 2700.0, 2700.0]
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터(polygon))

    with pytest.raises(GeometryError, match="면적 0"):
        localization_bbox(record)
