"""라벨 JSON 파서 실데이터 전수 테스트 — 94건. data/ 부재 환경에서는 자동 skip."""

from pathlib import Path

import pytest
from defect_agent.labels import Equipment, load_all_labels, representative_defect

라벨_루트 = Path("data/02.라벨링데이터")

pytestmark = pytest.mark.skipif(not 라벨_루트.exists(), reason="실데이터(data/) 없음")


@pytest.fixture(scope="module")
def records():
    return load_all_labels(라벨_루트)


def test_전건_94건_파싱(records):
    assert len(records) == 94


def test_QA_3변형_건수_일치(records):
    정상 = [r for r in records if r.is_normal]
    태양광_결함 = [r for r in records if not r.is_normal and r.equipment is Equipment.SOLAR]
    풍력_결함 = [r for r in records if not r.is_normal and r.equipment is Equipment.WIND]

    assert len(정상) == 17
    assert all(set(r.visionqa.questions) == {"detection"} for r in 정상)

    assert len(태양광_결함) == 3
    assert all(set(r.visionqa.questions) == {"detection", "localization"} for r in 태양광_결함)
    assert all(r.visionqa.cropped_bbox is None for r in 태양광_결함)

    assert len(풍력_결함) == 74
    assert all(
        set(r.visionqa.questions) == {"detection", "localization", "analysis", "classification"}
        for r in 풍력_결함
    )
    assert all(r.visionqa.cropped_bbox is not None for r in 풍력_결함)


def test_결함_폴더_속_정상_1건_판별(records):
    대상 = [r for r in records if r.stem == "2022_Sungsan_10_B_TrailingEdge_002"]
    assert len(대상) == 1
    assert 대상[0].is_normal is True


def test_풍력_74건_대표결함이_분류_정답과_일치(records):
    풍력_결함 = [r for r in records if not r.is_normal and r.equipment is Equipment.WIND]
    for r in 풍력_결함:
        대표 = representative_defect(r)
        문항 = r.visionqa.questions["classification"]
        assert 대표.category_name == 문항.options[문항.answer], r.stem


def test_풍력_대표결함_클래스_분포(records):
    """DATA_NOTES §6 집계 통계와 일치 — 파싱·선정 로직의 회귀 방지."""
    풍력_결함 = [r for r in records if not r.is_normal and r.equipment is Equipment.WIND]
    분포: dict[str, int] = {}
    for r in 풍력_결함:
        이름 = representative_defect(r).category_name
        분포[이름] = 분포.get(이름, 0) + 1
    assert 분포 == {
        "Paint Damage": 50,
        "Contamination": 14,
        "La Exposure": 5,
        "Bond Crack": 2,
        "La Damage": 1,
        "Rain Collar": 1,
        "Receptor Damage": 1,
    }
