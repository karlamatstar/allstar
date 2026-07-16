import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

const maxVus = __ENV.K6_VUS ? parseInt(__ENV.K6_VUS) : 200;
const totalDurationSec = __ENV.SCRIPT_DURATION ? parseInt(__ENV.SCRIPT_DURATION) : 60;

// Spike는 급격히 올렸다가 잠시 버티고 확 내립니다.
// 상승 10%, 유지 80%, 하강 10%
const spikeTime = Math.max(Math.floor(totalDurationSec * 0.1), 1) + 's';
const holdTime = Math.max(Math.floor(totalDurationSec * 0.8), 1) + 's';

export const options = {
    stages: [
        { duration: spikeTime, target: maxVus }, // 스파이크: 순식간에 최대 트래픽으로 급증
        { duration: holdTime, target: maxVus },  // 정점 유지
        { duration: spikeTime, target: 0 },      // 썰물: 순식간에 트래픽 감소
    ],
};

export default function () {
    const payload = JSON.stringify({
        question: "Spike 테스트 중입니다. 순간적인 폭주 상황입니다.",
        session_id: "spike_test"
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
