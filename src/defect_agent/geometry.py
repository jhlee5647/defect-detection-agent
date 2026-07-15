"""localization 정답 좌표 계산 — 채점기(U3)와 T4 크롭 로직이 공유하는 단일 구현 (ADR-0005).

풍력: 대표결함 폴리곤 → cropped_bbox 창 클리핑 → 타이트 bbox → 크롭 좌표계 변환.
태양광: 대표결함 bbox를 원본 좌표계에서 소수점 버림.
"""

import math

from defect_agent.labels import Equipment, LabelRecord, representative_defect


class GeometryError(ValueError):
    """좌표 계산이 불가능한 입력 — 데이터 또는 로직 이상 신호 (fail-fast)."""


def localization_bbox(record: LabelRecord) -> tuple[int, int, int, int]:
    """대표결함의 localization 정답 bbox [x, y, w, h] — 설비별 좌표계 규칙 적용."""
    defect = representative_defect(record)
    if defect is None:
        raise GeometryError(f"{record.stem}: 결함 annotation이 없어 좌표를 계산할 수 없음")

    if record.equipment is Equipment.SOLAR:
        return tuple(math.floor(v) for v in defect.bbox)

    window = record.visionqa.cropped_bbox  # 풍력 결함은 파서가 존재를 보장 (U1 변형 검증)
    points = list(zip(defect.polygon[0::2], defect.polygon[1::2], strict=True))
    clipped = clip_polygon_to_window(points, window)
    if not clipped:
        raise GeometryError(f"{record.stem}: 대표결함 폴리곤이 크롭 창과 겹치지 않음")
    xs, ys = [p[0] for p in clipped], [p[1] for p in clipped]
    x, y = min(xs) - window[0], min(ys) - window[1]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if w == 0 or h == 0:
        raise GeometryError(
            f"{record.stem}: 대표결함 폴리곤과 크롭 창의 겹침이 면적 0 — 경계 접촉만"
        )
    return (math.floor(x), math.floor(y), math.floor(w), math.floor(h))


def clip_polygon_to_window(
    points: list[tuple[float, float]], window: tuple[int, int, int, int]
) -> list[tuple[float, float]]:
    """폴리곤을 창 사각형으로 클리핑 (Sutherland–Hodgman) — 경계 위 점은 내부로 취급."""
    wx, wy, ww, wh = window
    edges = [
        (lambda p: p[0] >= wx, lambda p, q: _cross_x(p, q, wx)),
        (lambda p: p[0] <= wx + ww, lambda p, q: _cross_x(p, q, wx + ww)),
        (lambda p: p[1] >= wy, lambda p, q: _cross_y(p, q, wy)),
        (lambda p: p[1] <= wy + wh, lambda p, q: _cross_y(p, q, wy + wh)),
    ]
    for inside, cross in edges:
        result: list[tuple[float, float]] = []
        for i, p in enumerate(points):
            q = points[(i + 1) % len(points)]
            if inside(p):
                result.append(p)
            if inside(p) != inside(q):
                result.append(cross(p, q))
        points = result
        if not points:
            break
    return points


def _cross_x(p: tuple[float, float], q: tuple[float, float], x: float) -> tuple[float, float]:
    t = (x - p[0]) / (q[0] - p[0])
    return (x, p[1] + t * (q[1] - p[1]))


def _cross_y(p: tuple[float, float], q: tuple[float, float], y: float) -> tuple[float, float]:
    t = (y - p[1]) / (q[1] - p[1])
    return (p[0] + t * (q[0] - p[0]), y)
