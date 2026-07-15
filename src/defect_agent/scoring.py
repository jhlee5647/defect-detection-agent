"""VQA 채점기 — 에이전트 답안을 라벨 정답과 대조해 문항별 정오를 판정한다.

채점은 선지 문자 비교다. 정답률 집계·클래스별 분해는 U13 평가 실행의 몫이고,
localization 정답 좌표의 기하 계산은 geometry 모듈(ADR-0005 공유 구현)에 둔다.
"""

import json
from dataclasses import dataclass

from defect_agent.geometry import localization_bbox
from defect_agent.labels import LabelRecord, representative_defect


class ScoringError(ValueError):
    """채점 불가능한 입력 — 평가 하네스 버그 또는 데이터 이상 신호 (fail-fast)."""


_허용_오차_PX = 2  # DATA_NOTES §4 — 계산 bbox와 보기 값의 실측 오차 상한 ≤2px


def match_localization_option(options: dict[str, str], bbox: tuple[int, int, int, int]) -> str:
    """계산된 bbox와 좌표별 ±2px 이내인 보기를 고른다 — 유일하지 않으면 에러 (계획서 D1)."""
    matches = [
        letter
        for letter, text in sorted(options.items())
        if all(
            abs(a - b) <= _허용_오차_PX for a, b in zip(_parse_bbox_text(text), bbox, strict=True)
        )
    ]
    if len(matches) != 1:
        raise ScoringError(
            f"bbox {bbox}와 ±{_허용_오차_PX}px 이내 보기 {len(matches)}개 — 유일해야 함"
        )
    return matches[0]


def _parse_bbox_text(text: str) -> tuple[int, int, int, int]:
    """보기 텍스트 "[x,y,w,h]" → 정수 4개 (금일 실측 형식)."""
    try:
        values = json.loads(text)
    except json.JSONDecodeError as e:
        raise ScoringError(f"localization 보기 텍스트가 좌표 형식이 아님 — {text!r}") from e
    if not isinstance(values, list) or len(values) != 4:
        raise ScoringError(f"localization 보기는 좌표 4개여야 함 — {text!r}")
    return tuple(values)


# 94건 전수 실측 — detection 보기 텍스트는 {예, 아니오} 고정, 정답은 db_name과 94/94 일치
_DETECTION_정답_텍스트 = {True: "아니오", False: "예"}  # is_normal → 정답 보기 텍스트


def derive_answers(record: LabelRecord) -> dict[str, str]:
    """라벨의 정답 문자를 보지 않고 데이터에서 정답을 도출한다 — 자가 채점용.

    analysis는 다른 필드에서 독립 도출이 불가능하므로 포함하지 않는다 (계획서 D4).
    """
    questions = record.visionqa.questions
    answers = {
        "detection": _match_by_text(
            questions["detection"].options,
            _DETECTION_정답_텍스트[record.is_normal],
            f"{record.stem}: detection",
        )
    }
    if "localization" in questions:
        answers["localization"] = match_localization_option(
            questions["localization"].options, localization_bbox(record)
        )
    if "classification" in questions:
        answers["classification"] = _match_by_text(
            questions["classification"].options,
            representative_defect(record).category_name,
            f"{record.stem}: classification",
        )
    return answers


def _match_by_text(options: dict[str, str], text: str, ctx: str) -> str:
    matches = [letter for letter, value in sorted(options.items()) if value == text]
    if len(matches) != 1:
        raise ScoringError(f"{ctx}: 텍스트 {text!r}와 일치하는 보기 {len(matches)}개 — 유일해야 함")
    return matches[0]


@dataclass(frozen=True)
class ScoreResult:
    per_question: dict[str, bool]  # 문항종류 → 정답 여부 — E1/E2 집계가 직접 소비
    invalid: frozenset[str]  # 보기에 없는 선지 문자를 낸 문항 — 오답으로 집계됨 (계획서 D2)


def score_record(record: LabelRecord, answers: dict[str, str]) -> ScoreResult:
    """레코드에 있는 문항마다 답안의 선지 문자를 정답과 비교한다.

    답안의 문항 구성이 레코드와 다르면 모델 실력이 아니라 평가 하네스의 버그이므로
    오답 집계 대신 즉시 에러를 낸다 (계획서 D3).
    """
    expected, actual = set(record.visionqa.questions), set(answers)
    if actual != expected:
        누락, 여분 = sorted(expected - actual), sorted(actual - expected)
        raise ScoringError(f"{record.stem}: 답안 문항 불일치 — 누락 {누락}, 여분 {여분}")
    per_question: dict[str, bool] = {}
    invalid: set[str] = set()
    for kind, question in record.visionqa.questions.items():
        letter = answers[kind]
        if letter not in question.options:
            invalid.add(kind)
            per_question[kind] = False
        else:
            per_question[kind] = letter == question.answer
    return ScoreResult(per_question=per_question, invalid=frozenset(invalid))
