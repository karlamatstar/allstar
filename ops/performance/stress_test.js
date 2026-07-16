import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

const maxVus = __ENV.K6_VUS ? parseInt(__ENV.K6_VUS) : 100;
const totalDurationSec = __ENV.SCRIPT_DURATION ? parseInt(__ENV.SCRIPT_DURATION) : 120;

// 총 시간을 비율로 분할: 서서히 증가 25%, 최대 부하 50%, 쿨다운 25%
const rampUp = Math.max(Math.floor(totalDurationSec * 0.25), 1) + 's';
const hold = Math.max(Math.floor(totalDurationSec * 0.50), 1) + 's';
const rampDown = Math.max(Math.floor(totalDurationSec * 0.25), 1) + 's';

export const options = {
    stages: [
        { duration: rampUp, target: Math.floor(maxVus * 0.5) }, // 1단계: 절반의 부하로 상승
        { duration: rampUp, target: maxVus },                   // 2단계: 최대 부하 도달
        { duration: hold, target: maxVus },                     // 3단계: 최대 부하 유지
        { duration: rampDown, target: 0 },                      // 4단계: 부하 감소 (정상화)
    ],
};

export default function () {
    const payload = JSON.stringify({
        question: "Stress 테스트 중입니다. 서버가 언제 죽는지 확인합니다.",
        session_id: "stress_test"
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
