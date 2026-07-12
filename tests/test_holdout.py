"""홀드아웃 분할·유입 차단 단위 테스트 — 실측 분포를 합성 데이터로 재현한다."""

from pathlib import Path

from defect_agent.holdout import (
    HOLDOUT_SEED,
    load_manifest,
    scan_stores,
    split_holdout,
    write_manifest,
)
from defect_agent.labels import (
    Annotation,
    Equipment,
    FilenameParts,
    ImageMeta,
    LabelRecord,
    VisionQA,
)

실측_분포 = {
    "Paint Damage": 50,
    "Contamination": 14,
    "La Exposure": 5,
    "Bond Crack": 2,
    "La Damage": 1,
    "Rain Collar": 1,
    "Receptor Damage": 1,
}

승인_배분 = {"Paint Damage": 13, "Contamination": 4, "La Exposure": 2, "Bond Crack": 1}

_카테고리_ID = {이름: i + 1 for i, 이름 in enumerate(실측_분포)}


def _주석(클래스: str, 심각도: int = 1, 면적: float = 10.0) -> Annotation:
    return Annotation(
        id=1,
        category_id=_카테고리_ID[클래스],
        category_name=클래스,
        severity=심각도,
        area=면적,
        bbox=(0.0, 0.0, 10.0, 10.0),
        polygon=(0.0, 0.0, 10.0, 0.0, 10.0, 10.0),
    )


def _레코드(
    stem: str,
    equipment: Equipment = Equipment.WIND,
    is_normal: bool = False,
    클래스: str = "Paint Damage",
) -> LabelRecord:
    """분할 로직이 보는 필드(equipment·is_normal·annotations·stem)만 채운 합성 레코드."""
    if equipment is Equipment.WIND:
        파일명 = FilenameParts(
            year=2022, site="Sungsan", seq="001", unit="10", blade="A", part="LE"
        )
    else:
        파일명 = FilenameParts(year=2025, site="Eumseong", seq="00001", db_tag="Positive")
    return LabelRecord(
        stem=stem,
        equipment=equipment,
        is_normal=is_normal,
        filename=파일명,
        info={},
        collection={},
        image=ImageMeta(id=1, width=100, height=100, filename=f"{stem}.jpg"),
        categories={v: k for k, v in _카테고리_ID.items()},
        annotations=[] if is_normal else [_주석(클래스)],
        visionqa=VisionQA(object_description="", questions={}, cropped_bbox=None),
    )


def 실측_분포_레코드() -> list[LabelRecord]:
    """풍력 결함 74건 — DATA_NOTES §6 클래스 분포 그대로."""
    records = []
    for 클래스, 건수 in 실측_분포.items():
        for i in range(건수):
            stem = f"2022_Sungsan_10_A_{클래스.replace(' ', '')}_{i:03d}"
            records.append(_레코드(stem, 클래스=클래스))
    return records


# ---------------------------------------------------------------- 분할 규칙


def test_후보는_풍력_결함만():
    """정상·태양광 레코드는 홀드아웃 후보에서 제외된다 (평가는 풍력 결함 전용)."""
    records = 실측_분포_레코드() + [
        _레코드("2022_Sungsan_10_B_TrailingEdge_002", is_normal=True),
        _레코드("2025_Eumseong_Positive_00001", equipment=Equipment.SOLAR, 클래스="Paint Damage"),
        _레코드("2025_Eumseong_Normal_00001", equipment=Equipment.SOLAR, is_normal=True),
    ]
    split = split_holdout(records)
    풍력_결함_stems = {r.stem for r in 실측_분포_레코드()}
    assert set(split.stems) <= 풍력_결함_stems


def test_실측_분포에서_승인_배분표대로_뽑는다():
    """게이트 ①에서 승인한 배분표(13/4/2/1, 계 20)와 정확히 일치해야 한다."""
    split = split_holdout(실측_분포_레코드())
    assert {클래스: len(stems) for 클래스, stems in split.by_class.items()} == 승인_배분
    assert len(split.stems) == 20
    assert len(set(split.stems)) == 20


def test_1건_클래스는_홀드아웃에_없다():
    """희소 클래스(1건)는 인덱스 잔류 — 유사 사례 검색 평가를 가능하게 하기 위함."""
    split = split_holdout(실측_분포_레코드())
    for 희소 in ("La Damage", "Rain Collar", "Receptor Damage"):
        assert 희소 not in split.by_class


def test_모든_클래스가_인덱스에_최소_1건_남는다():
    """홀드아웃이 어떤 클래스도 전멸시키면 안 된다 (Bond Crack 2건 → 1/1)."""
    split = split_holdout(실측_분포_레코드())
    for 클래스, stems in split.by_class.items():
        assert len(stems) < 실측_분포[클래스]


def test_같은_시드는_같은_분할():
    records = 실측_분포_레코드()
    assert split_holdout(records) == split_holdout(records)


def test_다른_시드는_다른_선택():
    records = 실측_분포_레코드()
    assert split_holdout(records, seed=HOLDOUT_SEED).stems != split_holdout(records, seed=7).stems


def test_레코드_순서와_무관하게_같은_분할():
    """입력 순서가 달라도 결과가 같아야 재현성이 성립한다."""
    records = 실측_분포_레코드()
    assert split_holdout(records) == split_holdout(list(reversed(records)))


# ---------------------------------------------------------------- 매니페스트


def test_매니페스트_왕복(tmp_path: Path):
    """쓰고 다시 읽으면 동일한 분할이 복원된다."""
    split = split_holdout(실측_분포_레코드())
    경로 = tmp_path / "manifest.json"
    write_manifest(split, 경로)
    assert load_manifest(경로) == split


def test_매니페스트는_stem과_집계만_담는다(tmp_path: Path):
    """데이터 보안 — 캡션·좌표 등 라벨 내용이 매니페스트에 새면 안 된다."""
    split = split_holdout(실측_분포_레코드())
    경로 = tmp_path / "manifest.json"
    write_manifest(split, 경로)
    내용 = 경로.read_text(encoding="utf-8")
    assert "object_description" not in 내용
    assert "bbox" not in 내용


# ---------------------------------------------------------------- 유입 검사


def test_저장소_폴더_없으면_검사_대상_없음_통과(tmp_path: Path):
    assert scan_stores(tmp_path / "stores", ("2022_Sungsan_10_A_LeadingEdge_001",)) == []


def test_텍스트_파일_유입_검출(tmp_path: Path):
    stem = "2022_Sungsan_10_A_LeadingEdge_001"
    stores = tmp_path / "stores"
    stores.mkdir()
    (stores / "d1.sqlite").write_text(f"...{stem}...", encoding="utf-8")
    위반 = scan_stores(stores, (stem,))
    assert len(위반) == 1
    assert stem in 위반[0] and "d1.sqlite" in 위반[0]


def test_바이너리_파일_속_유입도_검출(tmp_path: Path):
    """Chroma·SQLite 내부 같은 바이너리에 박힌 stem도 잡아야 한다."""
    stem = "2022_Sungsan_10_A_LeadingEdge_001"
    stores = tmp_path / "stores"
    stores.mkdir()
    (stores / "v1.bin").write_bytes(b"\x00\x01" + stem.encode() + b"\xff\xfe")
    assert len(scan_stores(stores, (stem,))) == 1


def test_하위_폴더까지_재귀_검사(tmp_path: Path):
    stem = "2022_Sungsan_10_A_LeadingEdge_001"
    깊은_폴더 = tmp_path / "stores" / "v1" / "chroma"
    깊은_폴더.mkdir(parents=True)
    (깊은_폴더 / "segment.bin").write_bytes(stem.encode())
    assert len(scan_stores(tmp_path / "stores", (stem,))) == 1


def test_파일명에만_stem이_있어도_검출(tmp_path: Path):
    """적대적 리뷰 Major — stem 이름으로 저장된 크롭 이미지 등은 내용에 stem이 없다."""
    stem = "2022_Sungsan_10_A_LeadingEdge_001"
    폴더 = tmp_path / "stores" / "v1_crops"
    폴더.mkdir(parents=True)
    (폴더 / f"{stem}.jpg").write_bytes(b"\xff\xd8\xff\xe0 fake jpeg")
    assert len(scan_stores(tmp_path / "stores", (stem,))) == 1


def test_UTF16_내용_유입도_검출(tmp_path: Path):
    """적대적 리뷰 Minor — SQLite는 UTF-16 인코딩으로도 만들 수 있다."""
    stem = "2022_Sungsan_10_A_LeadingEdge_001"
    stores = tmp_path / "stores"
    stores.mkdir()
    (stores / "d1.sqlite").write_bytes(stem.encode("utf-16-le"))
    assert len(scan_stores(stores, (stem,))) == 1


def test_매니페스트_size_불일치는_에러(tmp_path: Path):
    """적대적 리뷰 Minor — size 필드와 stem 수가 어긋난 변조본은 로드를 거부한다."""
    import json

    import pytest

    경로 = tmp_path / "manifest.json"
    경로.write_text(
        json.dumps({"seed": 42, "size": 3, "by_class": {"Paint Damage": ["a", "b"]}}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError):
        load_manifest(경로)


def test_유입_없으면_통과(tmp_path: Path):
    stores = tmp_path / "stores"
    stores.mkdir()
    (stores / "d1.sqlite").write_bytes(b"2022_Sungsan_10_A_LeadingEdge_999")
    assert scan_stores(stores, ("2022_Sungsan_10_A_LeadingEdge_001",)) == []
