"""홀드아웃 분할 + 유입 차단 — 평가 20장의 봉인과 검사 (U2).

풍력 결함 74장에서 클래스 층화로 ~20장을 뽑아 매니페스트로 고정하고,
저장소(V1·V2·D1) 파일에 홀드아웃 stem이 유입되지 않았는지 검사한다.
분할 규칙·배분표는 U2 계획(게이트 ① 승인) 기준.
"""

import json
import random
from dataclasses import dataclass
from math import ceil
from pathlib import Path

from defect_agent.labels import Equipment, LabelRecord, representative_defect

HOLDOUT_SEED = 42
HOLDOUT_SIZE = 20
MANIFEST_PATH = Path(__file__).parent / "holdout_manifest.json"


@dataclass(frozen=True)
class HoldoutSplit:
    """홀드아웃 분할 결과 — 클래스명 → 봉인된 stem 목록(정렬)."""

    seed: int
    by_class: dict[str, tuple[str, ...]]

    @property
    def stems(self) -> tuple[str, ...]:
        """전체 홀드아웃 stem (정렬)."""
        return tuple(sorted(s for stems in self.by_class.values() for s in stems))


def _allocate(counts: dict[str, int], size: int) -> dict[str, int]:
    """클래스별 홀드아웃 장수 배분 — 비례(ceil) 기반, 1건 클래스는 인덱스 잔류.

    각 클래스가 인덱스에 최소 1건 남도록 상한(n-1)을 두고, ceil 합이 목표와
    어긋나면 배정 수가 가장 큰 클래스부터 조정한다 (동률은 이름순 — 결정적).
    """
    total = sum(counts.values())
    eligible = {c: n for c, n in counts.items() if n >= 2}
    alloc = {c: min(ceil(n * size / total), n - 1) for c, n in eligible.items()}
    while sum(alloc.values()) > size:
        biggest = max(alloc, key=lambda c: (alloc[c], c))
        alloc[biggest] -= 1
    while sum(alloc.values()) < size:
        여유 = [c for c in alloc if alloc[c] < eligible[c] - 1]
        if not 여유:
            raise ValueError(f"홀드아웃 {size}장을 채울 수 없음 — 후보 부족 (분포: {counts})")
        biggest = max(여유, key=lambda c: (eligible[c], c))
        alloc[biggest] += 1
    return {c: k for c, k in alloc.items() if k > 0}


def split_holdout(
    records: list[LabelRecord], size: int = HOLDOUT_SIZE, seed: int = HOLDOUT_SEED
) -> HoldoutSplit:
    """풍력 결함만 대상으로 클래스 층화 홀드아웃을 뽑는다 (대표결함 클래스 기준).

    같은 시드는 입력 순서와 무관하게 항상 같은 결과를 낸다 — 클래스·stem을
    정렬한 뒤 클래스 이름순으로 시드 고정 표본추출을 하기 때문.
    단 random.sample은 파이썬 버전 간 재현이 보장되지 않으므로, 봉인의 정본은
    커밋된 매니페스트이고 이 함수는 재현 증빙용이다 (달라지면 검사가 실패).
    """
    클래스별_stems: dict[str, list[str]] = {}
    for record in records:
        if record.equipment is not Equipment.WIND or record.is_normal:
            continue
        클래스 = representative_defect(record).category_name
        클래스별_stems.setdefault(클래스, []).append(record.stem)

    배분 = _allocate({c: len(s) for c, s in 클래스별_stems.items()}, size)
    rng = random.Random(seed)
    by_class = {
        클래스: tuple(sorted(rng.sample(sorted(클래스별_stems[클래스]), 배분[클래스])))
        for 클래스 in sorted(배분)
    }
    return HoldoutSplit(seed=seed, by_class=by_class)


def write_manifest(split: HoldoutSplit, path: Path = MANIFEST_PATH) -> None:
    """분할 결과를 매니페스트 JSON으로 기록한다 (stem·집계만 — 캡션·이미지 금지)."""
    data = {
        "seed": split.seed,
        "size": len(split.stems),
        "by_class": {c: list(stems) for c, stems in sorted(split.by_class.items())},
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_manifest(path: Path = MANIFEST_PATH) -> HoldoutSplit:
    """매니페스트 JSON을 읽어 HoldoutSplit으로 복원한다. size 불일치 변조는 거부."""
    data = json.loads(path.read_text(encoding="utf-8"))
    split = HoldoutSplit(
        seed=data["seed"],
        by_class={c: tuple(stems) for c, stems in data["by_class"].items()},
    )
    if data["size"] != len(split.stems):
        raise ValueError(f"{path}: size {data['size']} ≠ stem 수 {len(split.stems)} — 변조 의심")
    return split


def scan_stores(stores_dir: Path, stems: tuple[str, ...]) -> list[str]:
    """저장소 폴더의 파일 경로·내용을 검사해 홀드아웃 stem 유입을 찾는다.

    모든 저장소(Chroma·SQLite)는 레코드를 stem으로 키잉하므로, 유입되면 stem이
    파일 내용(UTF-8/UTF-16LE 평문 전제 — 압축·암호화 저장이면 미검출) 또는
    파일명(stem 키잉 캐시·크롭 파일)에 남는다.
    반환값은 위반 메시지 목록(비면 통과). 폴더가 없으면 검사 대상 없음 → 빈 목록.
    """
    if not stores_dir.exists():
        return []
    patterns = [(stem, (stem.encode("utf-8"), stem.encode("utf-16-le"))) for stem in stems]
    violations = []
    for file in sorted(p for p in stores_dir.rglob("*") if p.is_file()):
        상대경로 = file.relative_to(stores_dir).as_posix()
        content = file.read_bytes()
        for stem, encoded in patterns:
            if stem in 상대경로 or any(p in content for p in encoded):
                violations.append(f"{file}: 홀드아웃 stem '{stem}' 유입")
    return violations
