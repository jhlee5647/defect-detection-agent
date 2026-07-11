# ADR-0001. LLM/VLM을 Claude API 단일로 통일

- 상태: 승인 (2026-07-11, 소급 기록)

## Context

오케스트레이터(텍스트 LLM)와 vlm_analyze(VLM)의 모델 분리를 허용하고, 로컬 Qwen2.5-VL도 선택지로 제시한다. MVP 실행 환경은 GPU 없는 Windows PC 1대라 대형 모델 로컬 실행이 불가하다.

## Decision

오케스트레이터·text-to-SQL·자기검증·리포트 생성과 vlm_analyze 전부를 **Claude API 단일**로 구현한다. 기본 모델 claude-opus-4-8, 사용 버전은 설정에 고정·기록한다. 오케스트레이터는 텍스트 전용으로 호출하고 vlm_analyze만 vision 입력을 사용한다.

## Consequences

- (+) 모델 1종만 버전 관리, function calling·vision 모두 지원, 인프라 불필요.
- (−) 조건별 비용 분리 최적화(저가 라우팅 모델) 포기 — 샘플 94쌍 규모라 비용 영향 미미.
- LLM 접근은 인터페이스로 추상화해 모델 교체 여지를 남긴다 (SPEC §4 설계 원칙).
