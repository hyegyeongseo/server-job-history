// Step 1.5-B — k6 부하 테스트.
// 인증이 필요한 API라 setup()에서 로그인 → access 토큰을 받아 각 VU 요청에 Bearer로 붙인다.
// (엔드포인트는 실제 코드 기준: POST /api/auth/login/ → {"access": ...}, GET /api/jobs/)
//
// 실행:
//   k6 run -e BASE=http://<NODE-IP>:30080 -e U=loadtest -e P=loadtest-password load.js
// <NODE-IP> = kubectl get nodes -o wide 의 INTERNAL-IP
//
// ⚠️ 'loadtest' 유저가 실제로 있어야 200이 나온다. README.md 의 시드 명령 먼저 실행.

import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 50 },
    { duration: '2m', target: 200 },   // 램프업 — 여기서 CPU 70% 돌파 → HPA 2→N
    { duration: '1m', target: 0 },
  ],
};

const BASE = __ENV.BASE || 'http://<NODE-IP>:30080';

export function setup() {
  const res = http.post(
    `${BASE}/api/auth/login/`,
    JSON.stringify({
      username: __ENV.U || 'loadtest',
      password: __ENV.P || 'loadtest-password',
    }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  check(res, { 'login 200': (r) => r.status === 200 });
  return { token: res.json('access') };
}

export default function (data) {
  const params = { headers: { Authorization: `Bearer ${data.token}` } };
  const res = http.get(`${BASE}/api/jobs/`, params);
  check(res, { 'jobs 2xx/3xx': (r) => r.status < 400 });
  sleep(1);
}
