import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

export const options = {
    vus: 1,
    iterations: 1,
};

export default function () {
    // 1. Health Check
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
        'Health is status 200': (r) => r.status === 200,
    });

    // 2. Chat Mock Check
    const payload = JSON.stringify({
        question: "Smoke 테스트 요청입니다.",
        session_id: "test"
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
