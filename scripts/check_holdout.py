"""홀드아웃 차단 검사 — 커밋 전·인덱스 갱신 후 실행. 하나라도 어긋나면 exit 1.

검사 1 (재현성): 지금 코드로 분할을 다시 돌린 결과 = 커밋된 매니페스트인가.
검사 2 (유입): 저장소 폴더 파일들에 홀드아웃 stem이 등장하는가 (경로·바이트 검사).
경로는 저장소 루트 기준으로 해석하며, 수행된 검사가 0건이면 통과로 치지 않는다.
"""

import sys
from pathlib import Path

from defect_agent.holdout import load_manifest, scan_stores, split_holdout
from defect_agent.labels import load_all_labels
from defect_agent.settings import Settings

ROOT = Path(__file__).resolve().parents[1]


def _루트_기준(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    settings = Settings()
    manifest = load_manifest()
    print(f"매니페스트: 홀드아웃 {len(manifest.stems)}장 (seed={manifest.seed})")
    수행 = 0

    라벨_루트 = _루트_기준(settings.data_dir) / "02.라벨링데이터"
    if 라벨_루트.exists():
        if split_holdout(load_all_labels(라벨_루트)) != manifest:
            print("실패: 분할 재실행 결과가 매니페스트와 다름 — 분할 코드 변경 여부 확인")
            return 1
        print("재현성 검사: 통과 (분할 재실행 = 매니페스트)")
        수행 += 1
    else:
        print(f"재현성 검사: 생략 ({라벨_루트} 없음)")

    stores_dir = _루트_기준(settings.stores_dir)
    if stores_dir.exists():
        violations = scan_stores(stores_dir, manifest.stems)
        if violations:
            for v in violations:
                print(f"실패: {v}")
            return 1
        print(f"유입 검사: 통과 ({stores_dir} 오염 없음)")
        수행 += 1
    else:
        print(f"유입 검사: 대상 없음 ({stores_dir} 미생성)")

    if 수행 == 0:
        print("실패: 수행된 검사 0건 — 데이터·저장소가 모두 없어 통과 근거 없음")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
