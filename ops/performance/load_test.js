import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

const durationSec = __ENV.SCRIPT_DURATION ? parseInt(__ENV.SCRIPT_DURATION) : 60;

export const options = {
    vus: __ENV.K6_VUS ? parseInt(__ENV.K6_VUS) : 10,
    duration: durationSec + 's',
    thresholds: {
        http_req_failed: ['rate<0.05'], // 에러율 5% 미만
        http_req_duration: ['p(95)<3000'], // 95% 응답 3초 이내
    },
};

export default function () {
    const payload = JSON.stringify({
        question: "Load 테스트 중입니다. 잘 들리시나요?",
        session_id: "load_test"
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
