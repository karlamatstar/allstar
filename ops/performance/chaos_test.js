import http from 'k6/http';
import { check, sleep } from 'k6';

const TARGET_IP = __ENV.TARGET_IP || '127.0.0.1:8000';
const BASE_URL = `http://${TARGET_IP}`;

export const options = {
    vus: 1,
    iterations: 1,
};

export default function () {
    // FL-001: 정상 응답
    let res = http.get(`${BASE_URL}/fault-lab?scenario=normal`);
    check(res, { 'FL-001 normal is status 200': (r) => r.status === 200 });

    // FL-002: 응답 지연 1초
    res = http.get(`${BASE_URL}/fault-lab?scenario=delay&delay_seconds=1`);
    check(res, { 'FL-002 delay 1s is status 200': (r) => r.status === 200 });

    // FL-003: 응답 지연 5초
    res = http.get(`${BASE_URL}/fault-lab?scenario=delay&delay_seconds=5`, { timeout: '10s' });
    check(res, { 'FL-003 delay 5s is status 200': (r) => r.status === 200 });

    // FL-004: 500 오류 재현
    res = http.get(`${BASE_URL}/fault-lab?scenario=error500`);
    check(res, { 'FL-004 error500 is status 500': (r) => r.status === 500 });

    // FL-005: 타임아웃 재현
    res = http.get(`${BASE_URL}/fault-lab?scenario=timeout&delay_seconds=3`, { timeout: '10s' });
    check(res, { 'FL-005 timeout is status 504': (r) => r.status === 504 });

    // FL-006: 잘못된 시나리오
    res = http.get(`${BASE_URL}/fault-lab?scenario=wrong`);
    check(res, { 'FL-006 wrong is status 400': (r) => r.status === 400 });

    sleep(1);
}
