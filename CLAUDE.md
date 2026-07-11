# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

---

# 프로젝트 규칙 — 발전설비 결함진단 Agentic RAG

기존 행동 지침 4원칙은 그대로 적용된다. 아래는 이 프로젝트 고유 규칙이다.

## 개발 방법론 (요약)

- **SDD 3층**: 지시서 v1.1(전체 스펙) → docs/SPEC.md(MVP 범위 + 개발 단위 목록) → 단위별 계획(게이트 1에서 상세화). 점진 상세화 — 미리 전부 확정하지 않는다.
- **개발 단위**: 파일이 아니라 테스트 가능한 행위 단위. SPEC.md의 단위 목록 순서대로 진행.
- **TDD 4게이트 (핵심부)**: ① 계획 승인 → ② red(실패 테스트 + 실패 증거) 승인 → ③ green→refactor(통과 증거) 승인 → ④ 커밋 메시지 승인 → commit+push. 승인은 사용자의 명시 답변으로만 성립한다.
  - 풀 게이트 대상: 에이전트 그래프, 도구 4종, VQA 채점기, 인덱싱 파이프라인
  - 축소 게이트(계획+커밋 승인만): Gradio UI, 설정, 스캐폴딩, 일회성 스크립트
- **Git**: 기능 브랜치 → 개발 단위마다 commit+push → 기능 완료 시 PR로 main 머지. PR 머지 전 별도 컨텍스트의 적대적 리뷰 1회.

## 커밋 규칙

- 커밋 메시지는 **타입만 영어, 제목·본문은 한글** (예: `feat: VQA 채점기 폴리곤 클리핑 구현`). 영어 제목 금지.
- 커밋 전 pytest + ruff 통과 필수.
- 홀드아웃 평가 이미지(~20장)의 인덱스 유입 차단 검사를 통과해야 한다.

## 금지 상호작용 (지시서)

- 도구 간 직접 호출 금지 — 도구는 오케스트레이터(에이전트 그래프)만 호출한다.
- 도구의 S0(원본 데이터) 직접 접근 금지.
- 온라인 플레인에서 쓰기(인덱스·코퍼스 변경) 금지 — 쓰기는 오프라인 플레인 전용.

## 설계 원칙 4개 (클라우드 배포 대비 — 사용자 명시 요청 범위로 한정)

1. 벡터스토어·LLM 접근은 인터페이스로 추상화한다.
2. 설정은 외부화한다 (.env + pydantic-settings).
3. 온라인/오프라인 플레인 코드를 분리한다.
4. 에이전트 코어와 UI(Gradio)를 결합하지 않는다 — Gradio는 데모용, 서비스화 시 교체 전제.

## 데이터 보안

- `data/`는 절대 커밋하지 않는다 (.gitignore).
- docs/DATA_NOTES.md에는 스키마·규칙·집계 통계만 기록한다. 캡션 원문 전문 인용 금지, 이미지 포함 금지.

## 용어 규칙

- "포트폴리오", "취업용", "발주사" 단어를 대화·문서·코드 주석·커밋 메시지 어디에도 쓰지 않는다. 실제 업무로 상정하고 진행하며, 결정 주체는 사용자다.

## 기술 스택 (확정)

Claude API 단일(claude-opus-4-8 기본, 버전 기록) / Chroma(임베디드) / LangGraph / Gradio / SQLite / 임베딩 로컬(SigLIP + bge-m3). 평가는 풍력 전용(태양광은 인덱싱·UC-6 기능 데모만).