"""홀드아웃 차단 검사 — 커밋 전·인덱스 갱신 후 실행. 하나라도 어긋나면 exit 1.

검사 1 (재현성): 지금 코드로 분할을 다시 돌린 결과 = 커밋된 매니페스트인가.
검사 2 (유입): 저장소 폴더 파일들에 홀드아웃 stem이 등장하는가 (바이트 검사).
"""

import sys

from defect_agent.holdout import load_manifest, scan_stores, split_holdout
from defect_agent.labels import load_all_labels
from defect_agent.settings import Settings


def main() -> int:
    settings = Settings()
    manifest = load_manifest()
    print(f"매니페스트: 홀드아웃 {len(manifest.stems)}장 (seed={manifest.seed})")

    라벨_루트 = settings.data_dir / "02.라벨링데이터"
    if 라벨_루트.exists():
        if split_holdout(load_all_labels(라벨_루트)) != manifest:
            print("실패: 분할 재실행 결과가 매니페스트와 다름 — 분할 코드 변경 여부 확인")
            return 1
        print("재현성 검사: 통과 (분할 재실행 = 매니페스트)")
    else:
        print(f"재현성 검사: 생략 ({라벨_루트} 없음)")

    violations = scan_stores(settings.stores_dir, manifest.stems)
    if violations:
        for v in violations:
            print(f"실패: {v}")
        return 1
    if settings.stores_dir.exists():
        print(f"유입 검사: 통과 ({settings.stores_dir} 오염 없음)")
    else:
        print(f"유입 검사: 대상 없음 → 통과 ({settings.stores_dir} 미생성)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
