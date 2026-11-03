import http from 'k6/http';
import { check, sleep } from 'k6';

const base = __ENV.API_URL || 'http://127.0.0.1:8000';
const dashboard = __ENV.DASHBOARD_URL || 'http://127.0.0.1:4317';
export const options = {
  vus: 4, duration: '30s',
  summaryTrendStats: ['avg', 'med', 'p(95)', 'p(99)', 'max'],
  thresholds: { http_req_failed: ['rate<0.01'], http_req_duration: ['p(95)<500'] },
};
export function setup() {
  if (__ENV.AUTHORIZED_TARGET !== 'true') throw new Error('Set AUTHORIZED_TARGET=true for a reviewed test target');
}
export default function () {
  const responses = http.batch([
    ['GET', `${base}/api/v1/health`, null, { tags: { route: 'health' } }],
    ['GET', `${dashboard}/`, null, { tags: { route: 'dashboard' } }],
  ]);
  responses.forEach(r => check(r, { 'HTTP 200': r => r.status === 200 }));
  if (__ENV.WRITE_LOAD === 'true') {
    const r = http.post(`${base}/api/v1/jobs`, JSON.stringify({ name: 'load-fixture' }), {
      headers: { 'Content-Type': 'application/json' }, tags: { route: 'queue' },
      responseCallback: http.expectedStatuses(202, 429),
    });
    check(r, { 'accepted or backpressured': r => [202, 429].includes(r.status) });
  }
  sleep(0.1);
}
