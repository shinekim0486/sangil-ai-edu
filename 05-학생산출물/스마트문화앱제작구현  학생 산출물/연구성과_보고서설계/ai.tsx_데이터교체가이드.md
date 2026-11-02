# ai.tsx 데이터 교체 가이드

현재 `ai.tsx`의 `PRESETS`에는 연구회 보고서 예시용 수치가 포함되어 있다. 이 수치는 원자료에서 산출한 값으로 확인되지 않았으므로 최종 보고서의 연구결과로 사용하면 안 된다.

## 교체 순서

1. `rubric`의 `preScore`, `postScore`를 학생별 루브릭 원점수 집계값으로 교체한다.
2. `artifactMetrics`는 동일 학생의 전후 결과물 평가표에서 계산한다.
3. `efficiencyMetrics`는 실제 시작·완료 시각 또는 수업 기록이 있을 때만 계산한다.
4. `achievement`는 전문교과 평가 원점수와 사전에 확정한 A~E 기준으로 다시 계산한다.
5. `perception`은 동일 학생 사전·사후 응답만 매칭해 평균과 SD를 계산한다.
6. 모든 프리셋에 `sourceType`, `nPre`, `nPost`, `pairedN`, `verifiedAt` 필드를 추가한다.

## 권장 데이터 구조

```ts
{
  sourceType: 'actual' | 'simulated' | 'estimated',
  nPre: 34,
  nPost: 34,
  pairedN: 34,
  verifiedAt: '2026-10-30',
  limitations: []
}
```

대시보드 상단에는 자료 유형과 분석 대상 수를 항상 표시한다. `simulated` 또는 `estimated` 자료는 실제 연구 효과 카드와 KPI 합계에서 제외한다.
