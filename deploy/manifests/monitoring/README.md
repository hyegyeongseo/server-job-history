# 모니터링 스택 설치 (monitoring namespace)

관측 스택 = **메트릭(Prometheus)·로그(Loki)·트레이스(Tempo)·시각화(Grafana)·알림(Alertmanager→Slack)**.
ArgoCD는 앱(`server-job-manager`)만 관리한다. 이 디렉토리의 모니터링 리소스는 **수동(helm + kubectl)** 으로 아래 순서대로 올린다.

> 전제: `kubectl`/`helm` 사용 가능, 클러스터에 기본 StorageClass 존재(PVC용).

## 0) Helm 레포

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update
# chart 경로/이름은 환경에 따라 다를 수 있으니 helm search repo 로 확인:
#   helm search repo kube-prometheus-stack | loki | tempo | alloy
```

## 설치 순서 (의존성 순)

순서가 중요하다: **kps(=CRD 공급자) → 데이터 백엔드(Loki/Tempo) → 수집기(Alloy) → 글루(datasource/rule/dashboard) → 앱 연동**.

### 1) kube-prometheus-stack (kps) — Prometheus·Grafana·Alertmanager + CRD
릴리스 이름은 반드시 **`kps`** (다른 파일이 `release: kps` 라벨로 찾음).
```bash
helm install kps prometheus-community/kube-prometheus-stack \
  -n monitoring --create-namespace -f kps-values.yaml
```
이 단계가 ServiceMonitor/PrometheusRule **CRD**를 깐다 → 이후 servicemonitor·SLO 적용 가능.

### 2) Loki (로그 저장)
```bash
helm install loki grafana/loki -n monitoring -f loki-values.yaml
# 서비스 이름 확인(차트 모드에 따라 loki / loki-gateway):
kubectl -n monitoring get svc | grep loki
```

### 3) Tempo (트레이스, OTLP 수신)
```bash
helm install tempo grafana/tempo -n monitoring -f tempo-values.yaml
```

### 4) Alloy (파드 로그 → Loki)
```bash
helm install alloy grafana/alloy -n monitoring -f alloy-values.yaml
```

### 5) Grafana 글루 — 데이터소스/대시보드 (사이드카가 자동 등록)
```bash
kubectl apply -f loki-datasource.yaml
kubectl apply -f tempo-datasource.yaml
kubectl apply -f server-job-dashboard.yaml
```
> Prometheus 데이터소스는 kps가 자동 프로비저닝. Loki/Tempo는 위 ConfigMap(`grafana_datasource: "1"`)을 사이드카가 수십 초 내 잡는다.

### 6) SLO 룰 + Alertmanager Slack
```bash
# SLI 기록룰 + error-budget 알림
kubectl apply -f server-job-slo.yaml

# Slack webhook 은 git 에 안 넣는다 — 클러스터 Secret 으로:
kubectl -n monitoring create secret generic alertmanager-slack-webhook \
  --from-literal=url='https://hooks.slack.com/services/T.../B.../xxxx'

# Slack receiver 패치 (Secret 마운트 + config) 적용
helm upgrade kps prometheus-community/kube-prometheus-stack \
  -n monitoring --reuse-values -f alertmanager-values.yaml
```
> `alertmanager-values.yaml` 은 `api_url_file` 로 위 Secret(`/etc/alertmanager/secrets/alertmanager-slack-webhook/url`)을 읽는다. 평문 webhook 은 어디에도 커밋하지 않는다.

### 7) 앱 메트릭 스크랩 (앱 매니페스트 쪽)
앱 kustomize base에 포함됨(별도 적용 불필요, ArgoCD sync 시 함께):
`deploy/manifests/server-job-manager/base/servicemonitor.yaml` → Prometheus가 앱 `/metrics` 스크랩.

## 검증

```bash
# 전부 Running?
kubectl -n monitoring get pods

# Prometheus가 SLO 룰을 로드했나 / 앱 타깃이 UP인가
#   포트포워드 후 http://localhost:9090 → Status > Rules / Targets
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090

# Alertmanager가 Slack config를 먹었나
kubectl -n monitoring exec -it alertmanager-kps-kube-prometheus-stack-alertmanager-0 -c alertmanager -- \
  amtool config show --alertmanager.url=http://localhost:9093

# 테스트 알림 → #alerts 로 가는지
kubectl -n monitoring exec -it alertmanager-kps-kube-prometheus-stack-alertmanager-0 -c alertmanager -- \
  amtool alert add ErrorBudgetBurnFast severity=page \
  --annotation=summary="테스트 알림" \
  --annotation=runbook="https://github.com/hyegyeongseo/server-job-history/blob/main/docs/runbooks/error-budget.md" \
  --alertmanager.url=http://localhost:9093
```

## 파일 맵

| 파일 | 종류 | 적용 |
|---|---|---|
| `kps-values.yaml` | Helm values | `helm install kps` |
| `loki-values.yaml` / `tempo-values.yaml` / `alloy-values.yaml` | Helm values | 각 `helm install` |
| `alertmanager-values.yaml` | Helm values(패치) | `helm upgrade kps --reuse-values` |
| `loki-datasource.yaml` / `tempo-datasource.yaml` | ConfigMap(Grafana 사이드카) | `kubectl apply` |
| `server-job-dashboard.yaml` | ConfigMap(Grafana 사이드카) | `kubectl apply` |
| `server-job-slo.yaml` | PrometheusRule(SLI/SLO) | `kubectl apply` |

런북: [docs/runbooks/error-budget.md](../../../docs/runbooks/error-budget.md)

## 비밀 취급 (현재 → 향후)
- **현재**: `alertmanager-slack-webhook` 평문 Secret을 `kubectl` 로 수동 생성(git 미커밋).
- **향후**: sealed-secrets 도입 시 이 Secret을 `kubeseal` 로 암호화 → `SealedSecret` 으로 커밋. `alertmanager-values.yaml`(api_url_file 경로)은 변경 불필요.
