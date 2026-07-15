"""VQA 채점기 실데이터 전수 회귀 — 94건 자가 채점 (U3 완료 기준). data/ 부재 시 자동 skip.

자가 채점 = 라벨의 정답 문자를 보지 않고 데이터(db_name·폴리곤 기하·대표결함 카테고리)에서
정답을 도출해 채점기에 넣는 것. 전건 정답이면 채점기·기하·데이터 이해가 교차 증명된다.
조건부 skip의 강제 실행 게이트 = 커밋 전 로컬 pytest (계획서 §11 — 이 PC에는 data/가 있다).
"""

from pathlib import Path

import pytest

from defect_agent.labels import Equipment, load_all_labels
from defect_agent.scoring import derive_answers, score_record

라벨_루트 = Path("data/02.라벨링데이터")

pytestmark = pytest.mark.skipif(not 라벨_루트.exists(), reason="실데이터(data/) 없음")

# 수기 검증 결과 — 수정 금지, 수정은 사용자 승인 필요 (DATA_NOTES §1·§3)
풍력_결함_건수 = 74
태양광_결함_건수 = 3
정상_건수 = 17


@pytest.fixture(scope="module")
def records():
    return load_all_labels(라벨_루트)


def _자가_채점(record) -> dict[str, bool]:
    """도출 답안으로 채점하고, 도출된 문항의 정오만 돌려준다."""
    도출 = derive_answers(record)
    답안 = dict(도출)
    if "analysis" in record.visionqa.questions:
        # analysis는 독립 도출 불가(계획서 D4) — 채점기의 문항 구성 검사를 위해 라벨 정답으로 채움
        답안["analysis"] = record.visionqa.questions["analysis"].answer
    결과 = score_record(record, 답안)
    return {kind: 결과.per_question[kind] for kind in 도출}


def test_풍력_결함_74건_자가_채점_전건_정답(records):
    대상 = [r for r in records if not r.is_normal and r.equipment is Equipment.WIND]
    assert len(대상) == 풍력_결함_건수
    for record in 대상:
        정오 = _자가_채점(record)
        assert set(정오) == {"detection", "localization", "classification"}, record.stem
        assert all(정오.values()), f"{record.stem}: {정오}"


def test_태양광_결함_3건_자가_채점_전건_정답(records):
    대상 = [r for r in records if not r.is_normal and r.equipment is Equipment.SOLAR]
    assert len(대상) == 태양광_결함_건수
    for record in 대상:
        정오 = _자가_채점(record)
        assert set(정오) == {"detection", "localization"}, record.stem
        assert all(정오.values()), f"{record.stem}: {정오}"


def test_정상_17건_자가_채점_전건_정답(records):
    대상 = [r for r in records if r.is_normal]
    assert len(대상) == 정상_건수
    for record in 대상:
        정오 = _자가_채점(record)
        assert 정오 == {"detection": True}, record.stem
