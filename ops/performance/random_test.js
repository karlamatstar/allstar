import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

const durationSec = __ENV.SCRIPT_DURATION ? parseInt(__ENV.SCRIPT_DURATION) : 60;
const maxVus = __ENV.K6_VUS ? parseInt(__ENV.K6_VUS) : 100;

// 동적으로 stages 생성: 매 1초마다 1부터 maxVus 사이의 무작위 가상 유저 수를 설정
let randomStages = [];
for (let i = 0; i < durationSec; i++) {
    let randomVu = Math.floor(Math.random() * maxVus) + 1;
    randomStages.push({ duration: '1s', target: randomVu });
}

export const options = {
    // ramping-vus executor는 기본값이므로 stages 배열만 정의해도 작동합니다.
    stages: randomStages,
    thresholds: {
        http_req_failed: ['rate<0.05'], // 에러율 5% 미만
        http_req_duration: ['p(95)<3000'], // 95% 응답 3초 이내
    },
};

export default function () {
    const payload = JSON.stringify({
        question: "Random Load 테스트 중입니다. 잘 들리시나요?",
        session_id: "random_test"
    });

    const params = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const chatRes = http.post(`${BASE_URL}/chat_mock`, payload, params);

    check(chatRes, {
        'Chat Mock is status 200': (r) => r.status === 200,
    });

    sleep(1);
}
