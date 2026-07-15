"""VQA 채점기 테스트 — U3 계획서 테스트 목록(14개)을 한 번에 하나씩 구현한다.

픽스처는 U1 파서를 경유해 LabelRecord를 만든다 — 파서의 변형 검증을 통과한
레코드만 채점기에 들어온다는 실제 계약을 테스트에서도 그대로 재현하기 위함이다.
"""

import json

import pytest

from defect_agent.labels import parse_label_file
from defect_agent.scoring import (
    ScoringError,
    derive_answers,
    match_localization_option,
    score_record,
)

풍력_카테고리 = [
    {"id": 1, "name": "Contamination", "supercategory": "풍력 외부"},
    {"id": 3, "name": "Paint Damage", "supercategory": "풍력 외부"},
    {"id": 5, "name": "La Damage", "supercategory": "풍력 내부"},
]


def _문항(종류: str, 보기: dict[str, str], 정답: str) -> dict:
    return {
        f"defect_{종류}_q": f"{종류} 질문",
        f"defect_{종류}_option": {f"{종류}_option_{k}": v for k, v in 보기.items()},
        f"defect_{종류}_a": 정답,
    }


def 풍력_정상_데이터() -> dict:
    """정상 변형 — annotations 없음, 문항은 detection뿐 (DATA_NOTES §3)."""
    visionqa = {"object_description": "정상 블레이드 설명"}
    visionqa |= _문항("detection", {"a": "예", "b": "아니오"}, "b")
    return {
        "info": {"db_name": "NormalDB", "generator_name": "풍력", "part_side_tag": "Trailing Edge"},
        "collection": {"location": "Sungsan", "datetime": "2022-04-06 17:00:00"},
        "categories": 풍력_카테고리,
        "image": {
            "id": 2,
            "width": 8256,
            "height": 5504,
            "filename": "2022_Sungsan_10_B_TrailingEdge_002.jpg",
        },
        "visionqa": visionqa,
    }


def 풍력_결함_데이터() -> dict:
    """풍력 결함 변형 — 4문항 전체 + cropped_bbox. 결함 폴리곤은 크롭 창 완전 내부."""
    visionqa = {"object_description": "블레이드 표면 설명"}
    visionqa |= _문항("detection", {"a": "예", "b": "아니오"}, "a")
    visionqa |= _문항(
        "localization",
        {"a": "[1,2,3,4]", "b": "[199,251,100,50]", "c": "[9,10,11,12]", "d": "[13,14,15,16]"},
        "b",
    )
    visionqa |= _문항("analysis", {"a": "원인1", "b": "원인2", "c": "원인3", "d": "원인4"}, "c")
    visionqa |= _문항(
        "classification",
        {"a": "La Damage", "b": "Paint Damage", "c": "Contamination", "d": "Hot Spot"},
        "a",
    )
    visionqa["cropped_bbox"] = [2801, 2549, 1920, 1080]
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
                "segmentation": [3000.0, 2800.0, 3100.0, 2800.0, 3100.0, 2850.0],
                "area": 2500.0,
                "bbox": [3000.0, 2800.0, 100.0, 50.0],
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


풍력_결함_경로 = "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json"
풍력_정상_경로 = "WindBlade/B/TrailingEdge/2022_Sungsan_10_B_TrailingEdge_002.json"


# ── 테스트 1: 해피패스 기준선 ──


def test_해피패스_정답_답안은_전_문항_정답_판정(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    답안 = {"detection": "a", "localization": "b", "analysis": "c", "classification": "a"}

    결과 = score_record(record, 답안)

    assert 결과.per_question == {
        "detection": True,
        "localization": True,
        "analysis": True,
        "classification": True,
    }


# ── 테스트 2: 문항별 정오 독립 판정 ──


def test_틀린_문항만_오답이고_나머지는_영향_없음(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    답안 = {"detection": "a", "localization": "a", "analysis": "c", "classification": "b"}

    결과 = score_record(record, 답안)

    assert 결과.per_question == {
        "detection": True,
        "localization": False,
        "analysis": True,
        "classification": False,
    }


# ── 테스트 3: 정상 레코드는 detection만 채점 ──


def test_정상_레코드는_detection만_채점(tmp_path):
    record = _레코드(tmp_path, 풍력_정상_경로, 풍력_정상_데이터())

    결과 = score_record(record, {"detection": "b"})

    assert 결과.per_question == {"detection": True}


# ── 테스트 8: 계산 bbox ↔ localization 보기 매칭 (±2px 유일 선택) ──


def test_보기_매칭_2px_이내_보기를_유일_선택():
    보기 = {"a": "[1,2,3,4]", "b": "[199,251,100,50]", "c": "[9,10,11,12]", "d": "[13,14,15,16]"}

    # 계산값이 보기 b와 좌표별 최대 2px 차이 — DATA_NOTES §4 실측 오차 상한
    assert match_localization_option(보기, (200, 252, 101, 48)) == "b"
    # 정확히 일치하는 경우도 당연히 매칭
    assert match_localization_option(보기, (199, 251, 100, 50)) == "b"


# ── 테스트 9: 자가 채점용 정답 도출 — 라벨 정답 문자를 보지 않고 데이터에서 ──


def test_정답_도출_detection_localization_classification(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())

    도출 = derive_answers(record)

    # detection: PositiveDB → "예" 보기 / localization: 기하 계산 → 보기 b
    # classification: 대표결함 카테고리명(La Damage) → 보기 a
    # analysis는 독립 도출 불가 — 포함되지 않아야 한다 (계획서 D4)
    assert 도출 == {"detection": "a", "localization": "b", "classification": "a"}


# ── 테스트 10: 보기에 없는 선지 문자 — 에러가 아니라 오답 + 무효 표시 (계획서 D2) ──


def test_보기에_없는_선지_문자는_오답이며_무효_표시(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    답안 = {"detection": "e", "localization": "b", "analysis": "", "classification": "a"}

    결과 = score_record(record, 답안)

    # 모델이 지시를 안 따른 것도 측정 대상 — 평가를 중단시키지 않는다
    assert 결과.per_question == {
        "detection": False,
        "localization": True,
        "analysis": False,
        "classification": True,
    }
    assert 결과.invalid == frozenset({"detection", "analysis"})


def test_유효_답안이면_무효_표시_없음(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    답안 = {"detection": "a", "localization": "a", "analysis": "c", "classification": "a"}

    결과 = score_record(record, 답안)

    assert 결과.invalid == frozenset()


# ── 테스트 11: 답안-문항 구성 불일치 — 하네스 버그이므로 즉시 에러 (계획서 D3) ──


def test_문항_누락_답안은_즉시_에러(tmp_path):
    record = _레코드(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    누락_답안 = {"detection": "a", "localization": "b", "classification": "a"}  # analysis 없음

    with pytest.raises(ScoringError, match="analysis"):
        score_record(record, 누락_답안)


def test_여분_문항_답안은_즉시_에러(tmp_path):
    record = _레코드(tmp_path, 풍력_정상_경로, 풍력_정상_데이터())
    여분_답안 = {"detection": "b", "localization": "a"}  # 정상 레코드엔 localization 문항 없음

    with pytest.raises(ScoringError, match="localization"):
        score_record(record, 여분_답안)


# ── 테스트 12: 보기 매칭 유일성 위반 — 데이터 변형·기하 오류 감지 (계획서 D1) ──


def test_허용_오차_내_보기가_없으면_에러():
    보기 = {"a": "[1,2,3,4]", "b": "[199,251,100,50]", "c": "[9,10,11,12]", "d": "[13,14,15,16]"}

    with pytest.raises(ScoringError, match="0개"):
        match_localization_option(보기, (500, 500, 30, 30))


def test_허용_오차_내_보기가_복수면_에러():
    보기 = {
        "a": "[100,100,10,10]",
        "b": "[101,101,10,10]",
        "c": "[9,10,11,12]",
        "d": "[13,14,15,6]",
    }

    with pytest.raises(ScoringError, match="2개"):
        match_localization_option(보기, (100, 100, 10, 10))


def test_좌표_형식이_아닌_보기_텍스트는_에러():
    보기 = {"a": "왼쪽 위 영역", "b": "[199,251,100,50]"}

    with pytest.raises(ScoringError, match="좌표 형식"):
        match_localization_option(보기, (199, 251, 100, 50))
