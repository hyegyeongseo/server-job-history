# Sealed Secrets

평문 K8s Secret 을 git 에 커밋하지 않기 위해 **Bitnami sealed-secrets** 를 쓴다.
컨트롤러가 클러스터 안에서 비대칭 키쌍을 갖고, `kubeseal` 이 **공개키로 암호화**한 `SealedSecret`(=암호문)만 git 에 올린다. **복호화는 컨트롤러의 개인키로만** 되므로 암호문은 공개돼도 안전하다.

```
평문 Secret ──kubeseal(공개키)──> SealedSecret(암호문, git 커밋 OK)
                                      │ kubectl/ArgoCD apply
                                      ▼
                              컨트롤러(개인키 복호화) ──> 진짜 Secret(클러스터에만)
```

- `SealedSecret` 은 기본 **namespace+name 에 고정**(strict scope). 같은 이름이라도 다른 네임스페이스로는 복호화 안 됨 → 네임스페이스별로 따로 봉인.
- 진짜 Secret 은 컨트롤러가 생성/소유(ownerReference). git 에는 안 들어감.

---

## Phase 1 — 컨트롤러 + CLI 설치 (한 번)

### 1) 컨트롤러 (helm, kube-system)
`fullnameOverride=sealed-secrets-controller` 로 두면 kubeseal 기본값(kube-system/sealed-secrets-controller)과 맞아 플래그 없이 동작한다.
```bash
helm repo add sealed-secrets https://bitnami.github.io/sealed-secrets   # ★ bitnami-labs 아님(404)
helm repo update
helm install sealed-secrets sealed-secrets/sealed-secrets \
  -n kube-system --set-string fullnameOverride=sealed-secrets-controller
kubectl -n kube-system rollout status deploy/sealed-secrets-controller
```

### 2) kubeseal CLI (cp-1) — 컨트롤러와 버전 맞추기
```bash
# 컨트롤러 버전 확인
kubectl -n kube-system get deploy sealed-secrets-controller \
  -o jsonpath='{.spec.template.spec.containers[0].image}'; echo
# 그 버전으로 CLI 설치 (예: 0.38.1 — 위에서 확인한 값으로 치환)
KUBESEAL_VERSION=0.38.1
curl -sSL -o kubeseal.tgz \
  "https://github.com/bitnami-labs/sealed-secrets/releases/download/v${KUBESEAL_VERSION}/kubeseal-${KUBESEAL_VERSION}-linux-amd64.tar.gz"
tar xf kubeseal.tgz kubeseal && sudo install -m 755 kubeseal /usr/local/bin/kubeseal && rm kubeseal.tgz kubeseal
kubeseal --version
```

### 3) 동작 확인 — 공개 인증서 가져와지면 OK
```bash
kubeseal --fetch-cert   # PEM 인증서가 출력되면 정상
```

### 4) ⚠️ 봉인키(개인키) 백업 — 가장 중요
컨트롤러의 개인키를 잃으면 **모든 SealedSecret 을 영영 복호화 못 한다.** 클러스터 재구축 시에도 필요.
```bash
kubectl -n kube-system get secret \
  -l sealedsecrets.bitnami.com/sealed-secrets-key=active -o yaml > sealing-key-backup.yaml
```
> 이 파일은 **개인키 평문**이다. **git 에 절대 커밋 금지**, 비밀번호 매니저/오프라인 보관소에 보관.
> 복구 시: 새 클러스터에 이 secret 을 apply 후 컨트롤러 재시작하면 같은 키로 복호화 가능.

---

## 봉인 절차 (공통)

이미 클러스터에 있는 **live secret 을 그대로 봉인**(평문 다시 입력 불필요):
```bash
kubectl -n <NS> get secret <NAME> -o yaml \
  | kubeseal --format yaml \
  > <NAME>-sealed.yaml
```
- 기존 수동 secret 을 컨트롤러가 **인계(takeover)** 하게 하려면, **봉인 전에 live secret 에**
  `sealedsecrets.bitnami.com/managed=true` 주석을 단다(없으면 "이미 존재, SealedSecret 소유 아님" 에러):
  `kubectl -n <NS> annotate secret <NAME> sealedsecrets.bitnami.com/managed=true`
  (또는 기존 secret 을 먼저 지우고 apply)
- 적용: `kubectl apply -f <NAME>-sealed.yaml` (또는 ArgoCD sync) → 컨트롤러가 진짜 secret 생성.

---

## Phase 2 — 파일럿: alertmanager-slack-webhook (monitoring, 수동 apply)

```bash
# 1) live secret 봉인
kubectl -n monitoring get secret alertmanager-slack-webhook -o yaml \
  | kubeseal --format yaml \
  > deploy/manifests/sealed-secrets/alertmanager-slack-webhook-sealed.yaml

# 2) (인계) 위 파일 spec.template.metadata.annotations 에
#    sealedsecrets.bitnami.com/managed: "true" 추가  ── 또는 기존 secret 삭제
# 3) 적용 → 컨트롤러가 복호화해 동일 secret 재생성
kubectl apply -f deploy/manifests/sealed-secrets/alertmanager-slack-webhook-sealed.yaml
kubectl -n monitoring get secret alertmanager-slack-webhook -o jsonpath='{.metadata.ownerReferences[0].kind}'; echo
#   → SealedSecret 이면 인계 성공

# 4) git 커밋 (이 *-sealed.yaml 은 암호문이라 안전)
```
검증: Slack 테스트 알림이 여전히 가면(=api_url_file 이 복호화된 secret 을 읽음) 끝.

---

## Phase 3 — 앱 시크릿: ArgoCD (full GitOps)

대상(app ns): `server-job-manager-secret`, `regcred`.
(db ns 의 `postgres-secret` 도 같은 절차. `server-job-pg-app` 은 CNPG=Tier2 전환 시.)

```bash
kubectl -n app get secret server-job-manager-secret -o yaml | kubeseal --format yaml \
  > deploy/manifests/server-job-manager/base/server-job-manager-secret-sealed.yaml
kubectl -n app get secret regcred -o yaml | kubeseal --format yaml \
  > deploy/manifests/server-job-manager/base/regcred-sealed.yaml
```
- 두 파일을 `base/kustomization.yaml` 의 `resources:` 에 추가 → ArgoCD 가 sync → 컨트롤러가 복호화.
- 인계 충돌 피하려면 `managed: "true"` 주석을 넣거나, 최초 1회 기존 수동 secret 삭제.
- 이후 `00-create-secrets.sh` 의 수동 생성은 **부트스트랩(클러스터 최초 1회)용**으로만 남기고,
  정상 운영 시엔 SealedSecret 이 소스 오브 트루스가 된다.

> ArgoCD 주의: SealedSecret 은 git 에 있으니 ArgoCD 가 관리하지만, 그로부터 파생된 **진짜 Secret 은
> 컨트롤러 소유**라 ArgoCD 가 prune 하지 않는다(매니페스트에 없는 리소스는 건드리지 않음).

---

## 운영 메모
- **키 로테이션**: 컨트롤러는 30일(`--key-renew-period`)마다 새 봉인키를 **추가** 생성하고 옛 키도
  보관(기존 SealedSecret 복호화 유지). 새 키로는 새 봉인이 암호화된다. **키 생성 자체는 자동**이다.
- **봉인키 백업 자동화**: 새 키가 늘어나도 백업이 따라가도록 `sealing-key-backup-cronjob.yaml`
  (주 1회, cp-1 노드 `/var/backups/sealed-secrets` 에 active 키 전부 export). 수동 apply:
  `kubectl apply -f deploy/manifests/sealed-secrets/sealing-key-backup-cronjob.yaml`
  즉시 테스트: `kubectl -n kube-system create job --from=cronjob/sealed-secrets-key-backup keybackup-test`
  ⚠️ cp-1 디스크에 저장되므로 진짜 off-site 가 필요하면 그 디렉토리를 외부로 rsync/scp.
- **DR**: 클러스터 재구축 → 백업한 키 secret apply → 컨트롤러 설치/재시작 → 기존 SealedSecret 들 그대로 복호화.
- **무엇을 git 에 올리나**: `*-sealed.yaml`(암호문)·`sealing-key-backup-cronjob.yaml` = OK.
  봉인키 백업 산출물(개인키 평문)·`~/sealing-key-backup.yaml` = **절대 금지**.
