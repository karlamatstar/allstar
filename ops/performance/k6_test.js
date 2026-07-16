import http from "k6/http";
import { check, sleep } from "k6";

// 사용법: k6 run ops/performance/k6_test.js
// (BASE_URL 환경변수로 대상 서버를 바꿀 수 있음: k6 run -e BASE_URL=http://localhost:8000 ops/performance/k6_test.js)
const BASE_URL = __ENV.BASE_URL || "http://localhost:8000";

const QUESTIONS = [
  "이 교육과정은 총 몇 시간인가요?",
  "지각을 세 번 하면 어떻게 되나요?",
  "수료 조건이 어떻게 되나요?",
  "취업 지원은 어떤 걸 받을 수 있나요?",
];

export const options = {
  scenarios: {
    steady_load: {
      executor: "constant-vus",
      vus: 5,
      duration: "1m",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<20000"], // 저지/에이전트가 재시도(최대 3회, 각 20초 타임아웃)까지 가는 경우를 감안
  },
};

export default function () {
  const question = QUESTIONS[Math.floor(Math.random() * QUESTIONS.length)];
  const res = http.post(
    `${BASE_URL}/chat`,
    JSON.stringify({ question }),
    { headers: { "Content-Type": "application/json" } },
  );

  check(res, {
    "status is 200": (r) => r.status === 200,
    "answer is not empty": (r) => {
      try {
        return JSON.parse(r.body).answer.length > 0;
      } catch {
        return false;
      }
    },
  });

  sleep(1);
}
