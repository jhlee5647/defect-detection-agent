"""라벨 JSON 파서 — 라벨 94쌍을 읽는 단일 진입점.

DATA_NOTES.md의 실측 스키마와 함정 규칙(§7)을 여기서만 처리하고,
이후 단위(홀드아웃·채점기·이력 DB·인덱싱)는 이 모듈의 결과 객체만 소비한다.
형식이 어긋난 JSON은 건너뛰지 않고 LabelParseError를 즉시 발생시킨다.
"""

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class LabelParseError(ValueError):
    """라벨 JSON이 실측 스키마(DATA_NOTES)와 어긋날 때."""


class Equipment(Enum):
    WIND = "풍력"
    SOLAR = "태양광"


@dataclass(frozen=True)
class FilenameParts:
    """파일명 토큰 — 풍력 6개(unit·blade·part), 태양광 4개(db_tag)."""

    year: int
    site: str
    seq: str
    unit: str | None = None
    blade: str | None = None
    part: str | None = None
    db_tag: str | None = None


@dataclass(frozen=True)
class ImageMeta:
    id: int
    width: int
    height: int
    filename: str


@dataclass(frozen=True)
class Annotation:
    id: int
    category_id: int
    category_name: str
    severity: int
    area: float
    bbox: tuple[float, float, float, float]  # COCO [x, y, w, h] — 원본 좌표계
    polygon: tuple[float, ...]  # [x1, y1, x2, y2, ...] — 원본 좌표계


@dataclass(frozen=True)
class Question:
    text: str
    options: dict[str, str]  # "a"~"d" → 보기 텍스트 (원본의 문항별 접두어를 평탄화)
    answer: str  # "a"~"d"


@dataclass(frozen=True)
class VisionQA:
    object_description: str
    questions: dict[str, Question]  # detection / localization / analysis / classification
    cropped_bbox: tuple[int, int, int, int] | None  # 풍력 결함만 — 원본 좌표계 [x,y,1920,1080]


@dataclass(frozen=True)
class LabelRecord:
    stem: str
    equipment: Equipment
    is_normal: bool  # info.db_name 기준 (폴더 기준 아님)
    filename: FilenameParts
    info: dict
    collection: dict
    image: ImageMeta
    categories: dict[int, str]
    annotations: list[Annotation]  # 정상 라벨은 빈 리스트
    visionqa: VisionQA


_QUESTION_KINDS = ("detection", "localization", "analysis", "classification")
_EQUIPMENT_BY_GENERATOR = {"풍력": Equipment.WIND, "태양광": Equipment.SOLAR}
_IS_NORMAL_BY_DB = {"NormalDB": True, "PositiveDB": False}


def _require(data: dict, key: str, ctx: str):
    if key not in data:
        raise LabelParseError(f"{ctx}: 필수 키 '{key}' 부재")
    return data[key]


def _require_int(data: dict, key: str, ctx: str) -> int:
    value = _require(data, key, ctx)
    if not isinstance(value, int) or isinstance(value, bool):
        raise LabelParseError(f"{ctx}: '{key}'는 정수여야 함 — {value!r}")
    return value


def _number(value, ctx: str, what: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise LabelParseError(f"{ctx}: {what}이(가) 숫자가 아님 — {value!r}")
    return float(value)


def _parse_filename(stem: str, equipment: Equipment) -> FilenameParts:
    tokens = stem.split("_")
    expected = 6 if equipment is Equipment.WIND else 4
    if len(tokens) != expected:
        raise LabelParseError(
            f"{stem}: {equipment.value} 파일명은 {expected}토큰이어야 함 (실제 {len(tokens)})"
        )
    if not tokens[0].isdigit():
        raise LabelParseError(f"{stem}: 연도 토큰이 숫자가 아님 — '{tokens[0]}'")
    year, site = int(tokens[0]), tokens[1]
    if equipment is Equipment.WIND:
        return FilenameParts(
            year=year, site=site, unit=tokens[2], blade=tokens[3], part=tokens[4], seq=tokens[5]
        )
    if tokens[2] not in ("Normal", "Positive"):
        raise LabelParseError(f"{stem}: 태양광 3번째 토큰이 Normal/Positive가 아님 — '{tokens[2]}'")
    return FilenameParts(year=year, site=site, db_tag=tokens[2], seq=tokens[3])


def _parse_categories(raw: list, stem: str) -> dict[int, str]:
    categories: dict[int, str] = {}
    for entry in raw:
        cid, name = _require(entry, "id", stem), _require(entry, "name", stem)
        if categories.setdefault(cid, name) != name:
            raise LabelParseError(f"{stem}: 카테고리 id {cid} 이름 중복 정의 — '{name}'")
    return categories


def _parse_annotation(raw: dict, categories: dict[int, str], stem: str) -> Annotation:
    category_id = _require(raw, "category_id", stem)
    if category_id not in categories:
        raise LabelParseError(
            f"{stem}: annotations의 category_id {category_id}가 categories에 없음"
        )
    bbox = _require(raw, "bbox", stem)
    if len(bbox) != 4:
        raise LabelParseError(f"{stem}: bbox는 [x,y,w,h] 4개여야 함 (실제 {len(bbox)})")
    polygon = _require(raw, "segmentation", stem)
    if not isinstance(polygon, list) or len(polygon) < 6 or len(polygon) % 2 != 0:
        raise LabelParseError(f"{stem}: segmentation은 짝수 길이(≥6)의 평탄 리스트여야 함")
    return Annotation(
        id=_require_int(raw, "id", stem),
        category_id=category_id,
        category_name=categories[category_id],
        severity=_require_int(raw, "severity", stem),
        area=_number(_require(raw, "area", stem), stem, "area"),
        bbox=tuple(_number(v, stem, "bbox 원소") for v in bbox),
        polygon=tuple(_number(v, stem, "segmentation 원소") for v in polygon),
    )


def _parse_visionqa(raw: dict, stem: str) -> VisionQA:
    questions: dict[str, Question] = {}
    for kind in _QUESTION_KINDS:
        if f"defect_{kind}_q" not in raw:
            continue
        text = raw[f"defect_{kind}_q"]
        raw_options = _require(raw, f"defect_{kind}_option", stem)
        answer = _require(raw, f"defect_{kind}_a", stem)
        prefix = f"{kind}_option_"
        options: dict[str, str] = {}
        for key, value in raw_options.items():
            letter = key.removeprefix(prefix)
            if letter == key or letter not in ("a", "b", "c", "d"):
                raise LabelParseError(f"{stem}: {kind} 보기 키 형식 이상 — '{key}'")
            options[letter] = value
        if answer not in options:
            raise LabelParseError(f"{stem}: {kind} 정답 '{answer}'가 보기 {sorted(options)}에 없음")
        questions[kind] = Question(text=text, options=options, answer=answer)
    if "detection" not in questions:
        raise LabelParseError(f"{stem}: detection 문항 부재 — 모든 라벨의 필수 문항")

    cropped_bbox = raw.get("cropped_bbox")
    if cropped_bbox is not None:
        if len(cropped_bbox) != 4:
            raise LabelParseError(f"{stem}: cropped_bbox는 4개여야 함 (실제 {len(cropped_bbox)})")
        cropped_bbox = tuple(int(_number(v, stem, "cropped_bbox 원소")) for v in cropped_bbox)
    return VisionQA(
        object_description=_require(raw, "object_description", stem),
        questions=questions,
        cropped_bbox=cropped_bbox,
    )


def parse_label_file(path: Path | str) -> LabelRecord:
    """라벨 JSON 1개 → LabelRecord. 스키마 위반 시 LabelParseError."""
    path = Path(path)
    stem = path.stem
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise LabelParseError(f"{stem}: JSON 로드 실패 — {e}") from e

    info = _require(data, "info", stem)
    db_name = _require(info, "db_name", stem)
    if db_name not in _IS_NORMAL_BY_DB:
        raise LabelParseError(f"{stem}: db_name이 NormalDB/PositiveDB가 아님 — '{db_name}'")
    generator_name = _require(info, "generator_name", stem)
    if generator_name not in _EQUIPMENT_BY_GENERATOR:
        raise LabelParseError(f"{stem}: generator_name이 풍력/태양광이 아님 — '{generator_name}'")
    equipment = _EQUIPMENT_BY_GENERATOR[generator_name]
    _require(info, "part_side_tag", stem)  # D1 이력 DB(U4)의 부위 컬럼 소스 — 부재를 조기 검출

    image_raw = _require(data, "image", stem)
    image = ImageMeta(
        id=_require_int(image_raw, "id", stem),
        width=_require_int(image_raw, "width", stem),
        height=_require_int(image_raw, "height", stem),
        filename=_require(image_raw, "filename", stem),
    )
    categories = _parse_categories(_require(data, "categories", stem), stem)
    annotations = [_parse_annotation(a, categories, stem) for a in data.get("annotations", [])]
    record = LabelRecord(
        stem=stem,
        equipment=equipment,
        is_normal=_IS_NORMAL_BY_DB[db_name],
        filename=_parse_filename(stem, equipment),
        info=info,
        collection=_require(data, "collection", stem),
        image=image,
        categories=categories,
        annotations=annotations,
        visionqa=_parse_visionqa(_require(data, "visionqa", stem), stem),
    )
    _validate_variant(record)
    return record


_EXPECTED_QUESTIONS = {
    (Equipment.WIND, True): {"detection"},
    (Equipment.SOLAR, True): {"detection"},
    (Equipment.SOLAR, False): {"detection", "localization"},
    (Equipment.WIND, False): {"detection", "localization", "analysis", "classification"},
}


def _validate_variant(record: LabelRecord) -> None:
    """QA 변형 정합성(DATA_NOTES §3) — (설비, 정상여부)가 필드 구성을 결정한다."""
    expected = _EXPECTED_QUESTIONS[(record.equipment, record.is_normal)]
    actual = set(record.visionqa.questions)
    if actual != expected:
        raise LabelParseError(
            f"{record.stem}: 문항 구성 {sorted(actual)}이 변형 기대 {sorted(expected)}와 다름"
        )
    needs_crop = record.equipment is Equipment.WIND and not record.is_normal
    if (record.visionqa.cropped_bbox is not None) != needs_crop:
        raise LabelParseError(f"{record.stem}: cropped_bbox 유무가 변형(풍력 결함 전용)과 불일치")
    if record.is_normal == bool(record.annotations):
        raise LabelParseError(
            f"{record.stem}: db_name(정상={record.is_normal})과 annotations 유무가 모순"
        )
    tag = record.filename.db_tag
    if tag is not None and (tag == "Normal") != record.is_normal:
        raise LabelParseError(f"{record.stem}: 파일명 태그 '{tag}'와 db_name이 모순")


def representative_defect(record: LabelRecord) -> Annotation | None:
    """대표결함 선정 — 심각도 최고, 동률이면 면적 최대 (DATA_NOTES §4, 74/74 검증 완료)."""
    if not record.annotations:
        return None
    return max(record.annotations, key=lambda a: (a.severity, a.area))


def load_all_labels(root: Path | str) -> list[LabelRecord]:
    """root 아래 라벨 JSON 전체를 파싱하고 파일 간 일관성(카테고리·stem 유일성)을 검증한다."""
    records = [parse_label_file(p) for p in sorted(Path(root).rglob("*.json"))]
    seen_stems: set[str] = set()
    for record in records:
        if record.stem in seen_stems:
            raise LabelParseError(f"{record.stem}: stem 중복 — 하류 단위의 조인 키가 유일해야 함")
        seen_stems.add(record.stem)
    _validate_category_consistency(records)
    return records


def _validate_category_consistency(records: list[LabelRecord]) -> None:
    seen: dict[int, str] = {}
    for record in records:
        for cid, name in record.categories.items():
            if seen.setdefault(cid, name) != name:
                raise LabelParseError(
                    f"{record.stem}: 카테고리 id {cid} 이름 모순 — '{seen[cid]}' vs '{name}'"
                )
