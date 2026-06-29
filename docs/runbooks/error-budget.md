# Runbook: Error Budget Burn (가용성 SLO)

`ErrorBudgetBurnFast` 알림이 떴을 때 보는 문서입니다.
정의 출처: [deploy/manifests/monitoring/server-job-slo.yaml](../../deploy/manifests/monitoring/server-job-slo.yaml)

## SLO 요약

| 항목 | 값 |
|---|---|
| SLI | 가용성 = `2xx~4xx 응답 / 전체 응답` (5xx 만 실패로 집계) |
| SLO 목표 | **99%** (30일 롤링) |
| Error budget | 1% — 30일 기준 약 **7시간 18분** |
| 측정 지표 | `django_http_responses_total_by_status_total` (앱 `/metrics`, ServiceMonitor 스크랩) |

SLI 기록 룰:
- `sli:availability:ratio_rate5m` — 최근 5분 성공률
- `sli:availability:ratio_rate1h` — 최근 1시간 성공률

## 알림: ErrorBudgetBurnFast

```
(1 - sli:availability:ratio_rate5m) > (1 - 0.99) * 14.4
and
(1 - sli:availability:ratio_rate1h) > (1 - 0.99) * 14.4
for: 2m   →   severity: page
```

**의미:** 5분·1시간 window 에서 동시에 정상 대비 **14.4배 속도**로 에러 버짓을 태우는 중.
이 속도가 유지되면 30일치 버짓을 약 **2일 만에** 소진합니다. multi-window(5m + 1h) 조건이라
순간 스파이크가 아니라 "지속되는 장애"일 때만 page 합니다. 즉시 대응 대상입니다.

> **14.4 는 어디서 왔나 (출처·튜닝)**
> 산식 자체는 정의상 정확하다:
> - 발화 에러율 = `(1 - SLO) × burn_rate` = `0.01 × 14.4` = **14.4%**
> - 소진까지 = `SLO기간 / burn_rate` = `30일 / 14.4` ≈ **2일**
>
> 단, `14.4` 라는 값은 **"1시간 window 에서 30일 버짓의 2% 를 태우면 page"** 라는
> 선택에서 나온다(`burn_rate = 0.02 × 720h/1h = 14.4`). 이는 Google *The Site Reliability
> Workbook* — "Alerting on SLOs" 의 **권장 예시값**이지 공인 규격이 아니다. 환경에 맞게 조정 가능:
>
> | 태우는 양 / window | burn_rate | 등급 |
> |---|---|---|
> | 2% / 1h  | 14.4 | page (fast) ← 현재 |
> | 5% / 6h  | 6    | page |
> | 10% / 3일 | 1    | ticket (slow) |
>
> 더 민감하게 가려면 SLO 를 99.9% 로 올리거나 slow-burn(6×, 1×) 알림을 추가한다.

## 진단 순서

1. **무엇이 5xx 를 내는가** — Grafana → Explore(Prometheus):
   ```promql
   sum by (status) (rate(django_http_responses_total_by_status_total{status=~"5.."}[5m]))
   ```
   status(500/502/503/504) 분포로 1차 분류: 앱 예외(500) vs 게이트웨이/기동(502/503) vs 타임아웃(504).

2. **로그 확인** — Grafana → Explore(Loki):
   ```logql
   {namespace="app", app="server-job-manager"} |= "ERROR"
   ```
   500 급증이면 스택트레이스, 503 이면 readiness/DB 연결 메시지를 본다.

3. **트레이스 확인** — Grafana → Explore(Tempo): 느린/실패 트레이스에서 병목 span(DB 쿼리 등) 식별.
   (OTEL 이 켜져 있어야 함: `OTEL_TRACING_ENABLED=true`)

4. **자주 보는 원인 체크리스트**
   - **DB**: `kubectl -n db get pods`, 커넥션 고갈/다운 → readiness 503 → 5xx.
     비밀 불일치(503)는 [deploy/scripts/00-create-secrets.sh](../../deploy/scripts/00-create-secrets.sh) 참고(세 시크릿 동일 비번).
   - **배포 회귀**: `kubectl -n app rollout history deploy/server-job-manager` — 방금 올린 이미지가 원인인가.
   - **부하/포화**: `kubectl -n app get hpa server-job-manager` — CPU 70% 초과로 스케일 중인지, 한계(maxReplicas)인지.
   - **앱 기동**: 파드가 재시작 루프(`CrashLoopBackOff`)면 502/503.

## 완화(우선순위 순)

1. **배포가 원인이면 즉시 롤백** — 가장 빠른 버짓 출혈 차단:
   ```bash
   kubectl -n app rollout undo deploy/server-job-manager
   ```
   (ArgoCD 사용 중이면 self-heal 과 충돌하지 않게 해당 Application 에서 먼저 처리)
2. **포화면 증설** — HPA maxReplicas 상향 또는 일시적 수동 스케일:
   ```bash
   kubectl -n app scale deploy/server-job-manager --replicas=<N>
   ```
3. **DB 문제면** — 커넥션/풀/다운 복구. 비번 불일치면 시크릿 정합 후 파드 재시작.
4. 완화 후 `sli:availability:ratio_rate5m` 가 0.99 위로 회복되는지 확인 → 알림 resolved.

## 마무리

- 인시던트 노트(타임라인·원인·조치·재발방지) 기록.
- 같은 원인이 반복되면 SLO 임계/알림 window(`server-job-slo.yaml`)나 readiness/HPA 설정을 재검토.
