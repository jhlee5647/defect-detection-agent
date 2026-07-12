"""홀드아웃 분할 실데이터 테스트 — 커밋된 매니페스트와의 재현성 검사 포함.

data/ 부재 환경에서는 자동 skip. 매니페스트 대조 테스트가 pytest에 있으므로
커밋 전 pytest 통과 = 재현성 검사 통과가 상시 보장된다.
"""

from pathlib import Path

import pytest

from defect_agent.holdout import load_manifest, split_holdout
from defect_agent.labels import Equipment, load_all_labels

라벨_루트 = Path("data/02.라벨링데이터")

pytestmark = pytest.mark.skipif(not 라벨_루트.exists(), reason="실데이터(data/) 없음")


@pytest.fixture(scope="module")
def records():
    return load_all_labels(라벨_루트)


def test_실데이터_분할_승인_배분표_일치(records):
    split = split_holdout(records)
    assert {클래스: len(stems) for 클래스, stems in split.by_class.items()} == {
        "Paint Damage": 13,
        "Contamination": 4,
        "La Exposure": 2,
        "Bond Crack": 1,
    }
    assert len(split.stems) == 20


def test_홀드아웃은_전부_풍력_결함(records):
    split = split_holdout(records)
    stem별 = {r.stem: r for r in records}
    for stem in split.stems:
        record = stem별[stem]
        assert record.equipment is Equipment.WIND
        assert record.is_normal is False


def test_커밋된_매니페스트와_분할_일치(records):
    """재현성 검사의 본체 — 코드가 바뀌어 분할이 달라지면 여기서 잡힌다."""
    assert load_manifest() == split_holdout(records)
