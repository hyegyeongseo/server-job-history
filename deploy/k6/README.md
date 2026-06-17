# k6 부하 테스트

코드의 실제 엔드포인트 (`POST /api/auth/login/` → `{"access": ...}`, `GET /api/jobs/`)에 맞춰져 있습니다.

## 1) loadtest 유저 시드 (한 번만)

스크립트는 인증된 요청을 보내므로 `loadtest` 유저가 있어야 로그인 200이 납니다.
코드에 시드가 없으니 미리 만들어 둡니다:

```bash
kubectl -n app exec -it deploy/server-job-manager -- \
  python manage.py shell -c "from django.contrib.auth import get_user_model as G; U=G(); U.objects.filter(username='loadtest').exists() or U.objects.create_user('loadtest','','loadtest-password')"
```

## 2) 실행

```bash
NODE_IP=$(kubectl get nodes -o jsonpath='{.items[0].status.addresses[?(@.type=="InternalIP")].address}')
k6 run -e BASE=http://$NODE_IP:30080 -e U=loadtest -e P=loadtest-password load.js
```

## 3) 관찰 (다른 창)

```bash
watch -n1 'kubectl -n app get deploy,hpa server-job-manager'   # REPLICAS / TARGETS cpu%
```

응답 p99 우상향 → CPU 70% 돌파 → HPA 2→N → throughput 회복. before/after 튜닝 수치는
**ArgoCD Application 에 ignoreDifferences(/spec/replicas) 를 적용한 뒤** 재세요(안 그러면
self-heal↔HPA 플래핑이 그래프를 오염시킵니다).
