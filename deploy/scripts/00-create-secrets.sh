#!/usr/bin/env bash
# deploy/scripts/00-create-secrets.sh
# ─────────────────────────────────────────────────────────────────────────────
# 평문 시크릿 3개를 kubectl 로 한 번에 생성한다. git 에 커밋하지 않는다.
# DB 비밀번호를 "한 곳"에서만 정의 → 세 시크릿에 동일 주입 → 3곳 불일치(readiness 503) 원천 차단.
#
#   1) app ns  : server-job-manager-secret  (DJANGO_SECRET_KEY + DB_PASSWORD)        Tier 1
#   2) db  ns  : postgres-secret            (POSTGRES_PASSWORD)                       Tier 1
#   3) db  ns  : server-job-pg-app          (basic-auth: username + password)         Tier 2(CNPG)
#
# 사용법:
#   DB_PASSWORD="$(openssl rand -base64 24)" ./00-create-secrets.sh     # 새 비번 생성해서 사용
#   ./00-create-secrets.sh "<이미-정한-비번>"                            # 기존 비번 재사용
#
# ⚠️ 이미 클러스터가 돌고 있으면 반드시 "기존과 동일한" 비번을 넣을 것.
#    비번을 바꾸면 이미 그 비번으로 초기화된 postgres 의 인증이 깨진다(데이터 볼륨은 최초 비번을 기억).
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DB_PASSWORD="${DB_PASSWORD:-${1:-}}"
if [[ -z "${DB_PASSWORD}" ]]; then
  echo "ERROR: DB_PASSWORD 미지정." >&2
  echo "  예) DB_PASSWORD=\"\$(openssl rand -base64 24)\" $0" >&2
  echo "  또는) $0 \"<이미-정한-비번>\"" >&2
  exit 1
fi
DJANGO_SECRET_KEY="$(openssl rand -base64 50)"

# 네임스페이스 (없으면 생성)
for ns in app db; do
  kubectl get namespace "${ns}" >/dev/null 2>&1 || kubectl create namespace "${ns}"
done

# create | apply 패턴 = 멱등(이미 있으면 갱신, 없으면 생성). 'already exists' 에러 없이 재실행 가능.

# 1) 앱 Secret (app ns) ── Deployment / migrate-job 이 secretRef 로 참조
kubectl -n app create secret generic server-job-manager-secret \
  --from-literal=DJANGO_SECRET_KEY="${DJANGO_SECRET_KEY}" \
  --from-literal=DB_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 2) plain Postgres Secret (db ns, Tier 1) ── postgres StatefulSet 이 secretRef 로 참조
kubectl -n db create secret generic postgres-secret \
  --from-literal=POSTGRES_PASSWORD="${DB_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

# 3) CNPG 부트스트랩 Secret (db ns, Tier 2) ── basic-auth 타입 + username/password 키 필수
kubectl -n db create secret generic server-job-pg-app \
  --type=kubernetes.io/basic-auth \
  --from-literal=username=django_user \
  --from-literal=password="${DB_PASSWORD}" \
  --dry-run=client -o yaml | kubectl apply -f -

echo
echo "✅ 시크릿 3개 생성/갱신 완료 (app/server-job-manager-secret, db/postgres-secret, db/server-job-pg-app)"
echo "   DB_PASSWORD 는 세 시크릿에 동일하게 들어갔습니다. 이 값을 안전한 곳에 보관하세요."
