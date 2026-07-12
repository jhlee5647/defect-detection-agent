"""라벨 JSON 파서 단위 테스트 — DATA_NOTES 함정 케이스를 합성 데이터로 재현한다."""

import json

import pytest

from defect_agent.labels import (
    Equipment,
    LabelParseError,
    load_all_labels,
    parse_label_file,
    representative_defect,
)

풍력_카테고리 = [
    {"id": 1, "name": "Contamination", "supercategory": "풍력 외부"},
    {"id": 3, "name": "Paint Damage", "supercategory": "풍력 외부"},
    {"id": 5, "name": "La Damage", "supercategory": "풍력 내부"},
]

태양광_카테고리 = [{"id": 10, "name": "Hot Spot", "supercategory": "태양광 온도"}]

풍력_결함_경로 = "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json"
태양광_정상_경로 = "SolarPanel/Normal/PanelFront/2025_Eumseong_Normal_00001.json"
태양광_결함_경로 = "SolarPanel/Positive/PanelFront/2025_Eumseong_Positive_00001.json"


def _문항(종류: str, 보기: dict[str, str], 정답: str) -> dict:
    """visionqa 원본 구조의 문항 1개 — 문항별 접두어 중첩 dict (함정 B)."""
    return {
        f"defect_{종류}_q": f"{종류} 질문",
        f"defect_{종류}_option": {f"{종류}_option_{k}": v for k, v in 보기.items()},
        f"defect_{종류}_a": 정답,
    }


def _주석(id: int, category_id: int, severity: int, area: float) -> dict:
    return {
        "id": id,
        "image_id": 1,
        "category_id": category_id,
        "segmentation": [0.0, 0.0, 10.0, 0.0, 10.0, 10.0],
        "area": area,
        "bbox": [0.0, 0.0, 10.0, 10.0],
        "severity": severity,
    }


def 풍력_결함_데이터(annotations: list[dict] | None = None) -> dict:
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
        "annotations": annotations if annotations is not None else [_주석(1001, 5, 4, 100.0)],
        "visionqa": visionqa,
    }


def 풍력_정상_데이터() -> dict:
    """정상 라벨 — annotations 키 자체가 없고 QA는 detection만 (함정 C)."""
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


def 태양광_정상_데이터() -> dict:
    visionqa = {"object_description": "정상 패널 설명"}
    visionqa |= _문항("detection", {"a": "예", "b": "아니오"}, "b")
    return {
        "info": {"db_name": "NormalDB", "generator_name": "태양광", "part_side_tag": "Front"},
        "collection": {"location": "Eumseong", "datetime": "2025-05-01 10:00:00"},
        "categories": 태양광_카테고리,
        "image": {
            "id": 100001,
            "width": 640,
            "height": 512,
            "filename": "2025_Eumseong_Normal_00001.jpg",
        },
        "visionqa": visionqa,
    }


def 태양광_결함_데이터() -> dict:
    """태양광 결함 변형 — detection + localization, cropped_bbox 없음 (DATA_NOTES §3)."""
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
        "categories": 태양광_카테고리,
        "image": {
            "id": 118506,
            "width": 640,
            "height": 512,
            "filename": "2025_Eumseong_Positive_00001.jpg",
        },
        "annotations": [_주석(118506001, 10, 3, 37.0)],
        "visionqa": visionqa,
    }


def _저장(tmp_path, 상대경로: str, 데이터: dict):
    경로 = tmp_path / 상대경로
    경로.parent.mkdir(parents=True, exist_ok=True)
    경로.write_text(json.dumps(데이터, ensure_ascii=False), encoding="utf-8")
    return 경로


# ── 함정 A: 정상/결함 판별은 폴더가 아니라 db_name ──


def test_함정A_결함_폴더_속_정상_라벨은_db_name으로_판별(tmp_path):
    경로 = _저장(
        tmp_path,
        "WindBlade/B/TrailingEdge/2022_Sungsan_10_B_TrailingEdge_002.json",
        풍력_정상_데이터(),
    )
    record = parse_label_file(경로)
    assert record.is_normal is True
    assert record.equipment is Equipment.WIND


# ── 함정 B: 문항별 접두어 중첩 옵션 → 통일 형태로 평탄화 ──


def test_함정B_문항별_접두어_옵션을_a부터d로_평탄화(tmp_path):
    경로 = _저장(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    record = parse_label_file(경로)
    questions = record.visionqa.questions
    assert set(questions) == {"detection", "localization", "analysis", "classification"}
    classification = questions["classification"]
    assert set(classification.options) == {"a", "b", "c", "d"}
    assert classification.options["a"] == "La Damage"
    assert classification.answer == "a"
    assert set(questions["detection"].options) == {"a", "b"}


# ── 함정 C: annotations 부재(정상 17건)는 정상 흐름 ──


def test_함정C_annotations_부재는_빈_리스트로_처리(tmp_path):
    경로 = _저장(tmp_path, 태양광_정상_경로, 태양광_정상_데이터())
    record = parse_label_file(경로)
    assert record.annotations == []
    assert set(record.visionqa.questions) == {"detection"}
    assert record.visionqa.cropped_bbox is None
    assert representative_defect(record) is None


# ── 함정 D: 파일명 토큰 — 풍력 6개 / 태양광 4개 ──


def test_함정D_풍력_파일명_6토큰_분해(tmp_path):
    경로 = _저장(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    parts = parse_label_file(경로).filename
    assert (parts.year, parts.site, parts.unit, parts.blade, parts.part, parts.seq) == (
        2022,
        "Sungsan",
        "10",
        "A",
        "LeadingEdge",
        "001",
    )


def test_함정D_태양광_파일명_4토큰_분해(tmp_path):
    경로 = _저장(tmp_path, 태양광_정상_경로, 태양광_정상_데이터())
    parts = parse_label_file(경로).filename
    assert (parts.year, parts.site, parts.db_tag, parts.seq) == (
        2025,
        "Eumseong",
        "Normal",
        "00001",
    )
    assert parts.unit is None and parts.blade is None and parts.part is None


def test_함정D_토큰_수_불일치는_에러(tmp_path):
    경로 = _저장(tmp_path, "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_001.json", 풍력_결함_데이터())
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


# ── 대표결함 선정: 심각도 최고 → 동률 시 면적 최대 ──


def test_대표결함_심각도_최고_선정(tmp_path):
    데이터 = 풍력_결함_데이터(annotations=[_주석(1, 3, 2, 999.0), _주석(2, 5, 4, 10.0)])
    경로 = _저장(tmp_path, "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json", 데이터)
    대표 = representative_defect(parse_label_file(경로))
    assert 대표.id == 2
    assert 대표.category_name == "La Damage"


def test_대표결함_심각도_동률이면_면적_최대(tmp_path):
    데이터 = 풍력_결함_데이터(annotations=[_주석(1, 3, 3, 10.0), _주석(2, 1, 3, 99.0)])
    경로 = _저장(tmp_path, "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json", 데이터)
    대표 = representative_defect(parse_label_file(경로))
    assert 대표.id == 2


# ── 에러 정책: 형식 이상은 조용히 넘어가지 않고 즉시 에러 ──


@pytest.mark.parametrize(
    "훼손",
    [
        pytest.param(lambda d: d.pop("visionqa"), id="visionqa_키_부재"),
        pytest.param(lambda d: d["info"].update(db_name="UnknownDB"), id="db_name_비정상"),
        pytest.param(lambda d: d["info"].update(generator_name="수력"), id="generator_name_비정상"),
        pytest.param(
            lambda d: d["visionqa"].update(defect_detection_a="z"), id="정답이_보기에_없음"
        ),
        pytest.param(lambda d: d["annotations"][0].pop("severity"), id="severity_부재"),
        pytest.param(lambda d: d["info"].pop("part_side_tag"), id="part_side_tag_부재"),
        pytest.param(lambda d: d["annotations"][0].update(severity="3"), id="severity가_문자열"),
        pytest.param(
            lambda d: d["annotations"][0].update(segmentation=[[0.0, 0.0, 10.0, 0.0, 10.0, 10.0]]),
            id="segmentation_중첩_리스트",
        ),
        pytest.param(
            lambda d: d["annotations"][0].update(segmentation=[0.0, 0.0, 10.0, 0.0, 10.0]),
            id="segmentation_홀수_길이",
        ),
        pytest.param(
            lambda d: d["annotations"][0].update(bbox=[0.0, "x", 10.0, 10.0]),
            id="bbox_원소가_비숫자",
        ),
    ],
)
def test_형식_이상은_즉시_에러(tmp_path, 훼손):
    데이터 = 풍력_결함_데이터()
    훼손(데이터)
    경로 = _저장(tmp_path, "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_001.json", 데이터)
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_깨진_JSON은_에러(tmp_path):
    경로 = tmp_path / 풍력_결함_경로
    경로.parent.mkdir(parents=True)
    경로.write_text("{ 깨진 json", encoding="utf-8")
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_파일_부재는_에러(tmp_path):
    with pytest.raises(LabelParseError):
        parse_label_file(tmp_path / "2022_Sungsan_10_A_LeadingEdge_001.json")


# ── 변형 정합성: (설비, 정상여부)가 문항·cropped_bbox·annotations 구성을 결정 ──


def _classification_문항_제거(d):
    for 키 in [k for k in d["visionqa"] if "classification" in k]:
        d["visionqa"].pop(키)


@pytest.mark.parametrize(
    "훼손",
    [
        pytest.param(lambda d: d.pop("annotations"), id="결함인데_annotations_키_부재"),
        pytest.param(lambda d: d.update(annotations=[]), id="결함인데_annotations_빈_리스트"),
        pytest.param(_classification_문항_제거, id="풍력_결함인데_classification_부재"),
        pytest.param(
            lambda d: d["visionqa"].pop("cropped_bbox"), id="풍력_결함인데_cropped_bbox_부재"
        ),
    ],
)
def test_변형_정합성_풍력_결함_위반은_에러(tmp_path, 훼손):
    데이터 = 풍력_결함_데이터()
    훼손(데이터)
    경로 = _저장(tmp_path, 풍력_결함_경로, 데이터)
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_변형_정합성_정상인데_annotations_존재는_에러(tmp_path):
    데이터 = 풍력_정상_데이터()
    데이터["annotations"] = [_주석(1, 3, 2, 10.0)]
    경로 = _저장(
        tmp_path, "WindBlade/B/TrailingEdge/2022_Sungsan_10_B_TrailingEdge_002.json", 데이터
    )
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_변형_정합성_태양광_결함인데_cropped_bbox_존재는_에러(tmp_path):
    데이터 = 태양광_결함_데이터()
    데이터["visionqa"]["cropped_bbox"] = [0, 0, 640, 512]
    경로 = _저장(tmp_path, 태양광_결함_경로, 데이터)
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_변형_정합성_태양광_파일명_태그와_db_name_불일치는_에러(tmp_path):
    경로 = _저장(tmp_path, 태양광_정상_경로, 태양광_결함_데이터())  # 파일명 Normal + PositiveDB
    with pytest.raises(LabelParseError):
        parse_label_file(경로)


def test_변형_정합성_태양광_결함은_통과(tmp_path):
    record = parse_label_file(_저장(tmp_path, 태양광_결함_경로, 태양광_결함_데이터()))
    assert record.is_normal is False
    assert set(record.visionqa.questions) == {"detection", "localization"}
    assert record.visionqa.cropped_bbox is None


# ── 전체 로드 + 카테고리 일관성 검증 ──


def test_전체_로드_건수(tmp_path):
    _저장(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    _저장(tmp_path, 태양광_정상_경로, 태양광_정상_데이터())
    records = load_all_labels(tmp_path)
    assert len(records) == 2


def test_파일_간_카테고리_모순은_에러(tmp_path):
    _저장(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    모순 = 풍력_결함_데이터()
    모순["categories"] = [{"id": 3, "name": "Tape Damage", "supercategory": "풍력 외부"}]
    모순["annotations"] = [_주석(1, 3, 2, 10.0)]
    모순["visionqa"]["defect_classification_option"]["classification_option_a"] = "Tape Damage"
    모순["image"]["filename"] = "2022_Sungsan_10_A_LeadingEdge_002.jpg"
    _저장(tmp_path, "WindBlade/A/LeadingEdge/2022_Sungsan_10_A_LeadingEdge_002.json", 모순)
    with pytest.raises(LabelParseError):
        load_all_labels(tmp_path)


def test_stem_중복은_에러(tmp_path):
    _저장(tmp_path, 풍력_결함_경로, 풍력_결함_데이터())
    다른_폴더_경로 = "WindBlade/B/PressureSide/2022_Sungsan_10_A_LeadingEdge_001.json"
    _저장(tmp_path, 다른_폴더_경로, 풍력_결함_데이터())
    with pytest.raises(LabelParseError):
        load_all_labels(tmp_path)
